#!/usr/bin/env python3
from time import sleep
import boto3

INSTANCE_ID = 'i-abcd1234'
AWS_REGION = 'us-west-2'
CMK = 'arn:aws:kms:us-west-2:123456789012:key/12345678-1234-abcd-5678-abcd1234'

ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
ec2_client = boto3.client('ec2', region_name=AWS_REGION)

ec2_instance = ec2_resource.Instance(INSTANCE_ID)

# Get the current block device mappings

print('\n===== Checking', ec2_instance.id, '=====')

az = ec2_instance.placement['AvailabilityZone']
print(ec2_instance.placement['AvailabilityZone'])

for device in ec2_instance.block_device_mappings:
    print(device['DeviceName'], device['Ebs']['VolumeId'])

# Describe snapshot status for this instance 

snapshots = ec2_resource.snapshots.filter(
    Filters=[
        {
            'Name': 'tag:instance',
            'Values': [
                INSTANCE_ID
            ]
        }
    ]
)

for snapshot in snapshots:
    print(snapshot.id, snapshot.progress, snapshot.volume_id, snapshot.volume_size, snapshot.start_time.strftime("%H:%M:%S"))
    fsr_status = ec2_client.describe_fast_snapshot_restores(
        Filters=[
            {
                'Name': 'snapshot-id',
                'Values': [
                    snapshot.id
                ]
            },
        ]
    )
    if fsr_status['FastSnapshotRestores']:
        if fsr_status['FastSnapshotRestores'][0]['State'] == 'enabled':
            print(snapshot.id, 'FSR enabled with OptimizingTime', fsr_status['FastSnapshotRestores'][0]['OptimizingTime'].strftime("%H:%M:%S"),
                  'and EnabledTime', fsr_status['FastSnapshotRestores'][0]['EnabledTime'].strftime("%H:%M:%S"))
        else:
            print(snapshot.id, 'FSR in', fsr_status['FastSnapshotRestores'][0]['State'], 'state', 
                  'with OptimizingTime', fsr_status['FastSnapshotRestores'][0]['OptimizingTime'].strftime("%H:%M:%S"))
    else:
        print('FSR might not be enabled.')

if ec2_instance.state['Name'] != 'stopped':
    print('\n!!! Please stop the instance before moving on !!!')

print('\nMoving on to create the volumes? (Y/N)')
confirm = input()

if confirm == 'Y':
    print('\n=====', ec2_instance.id, '-', ec2_instance.state['Name'], '=====')
    print('=== Current block device mapping ===')

    for device in ec2_instance.block_device_mappings:
        print(device['DeviceName'], device['Ebs']['VolumeId'])

    for device in ec2_instance.block_device_mappings:

        print('\nAbout to replace', device['Ebs']['VolumeId'], 'on', device['DeviceName'])
        print('Moving on? (Y/N)')
        confirm = input()
        if confirm != 'Y':
            break

        for snapshot in snapshots:
            if snapshot.volume_id == device['Ebs']['VolumeId']:
                print(snapshot.id, 'is taken from', snapshot.volume_id)
                
                # Create the volume 

                print('\nCreating a volume based on the snapshot.')

                created_volume = ec2_client.create_volume(
                    AvailabilityZone = az,
                    Encrypted = True,
                    KmsKeyId = CMK,
                    SnapshotId = snapshot.id,
                    VolumeType = 'gp3',
                    TagSpecifications=[
                        {
                            'ResourceType': 'volume',
                            'Tags': [
                                {
                                    'Key': 'original_volume',
                                    'Value': device['Ebs']['VolumeId']
                                },
                                {
                                    'Key': 'instance',
                                    'Value': ec2_instance.id
                                },
                            ]
                        },
                    ],

                )
                
                # Wait for the volume to become available 

                while True:
                    check_volume_status = ec2_client.describe_volumes(
                                        VolumeIds = [
                                            created_volume['VolumeId']
                                        ])
                    if check_volume_status['Volumes'][0]['State'] == 'available':
                        print(check_volume_status['Volumes'][0]['VolumeId'], 'created!')
                        break
                    else:
                        print(check_volume_status['Volumes'][0]['VolumeId'], 'is still', check_volume_status['Volumes'][0]['State'])
                        sleep(2)



                # Detach the original volume

                print('\nDetaching volume', device['Ebs']['VolumeId'])

                ec2_instance.detach_volume(
                    VolumeId = device['Ebs']['VolumeId']
                )

                while True:
                    check_volume_status = ec2_client.describe_volumes(
                                        VolumeIds = [
                                            device['Ebs']['VolumeId']
                                        ])
                    if check_volume_status['Volumes'][0]['State'] == 'available':
                        print(check_volume_status['Volumes'][0]['VolumeId'], 'detached!')
                        break
                    else:
                        print(check_volume_status['Volumes'][0]['VolumeId'], 'is still', check_volume_status['Volumes'][0]['State'])
                        sleep(2)

                # Attach the new volume 

                print('\nAttaching volume', created_volume['VolumeId'], 'on', device['DeviceName'])

                ec2_instance.attach_volume(
                    VolumeId = created_volume['VolumeId'],
                    Device = device['DeviceName']
                )

                while True:
                    check_volume_status = ec2_client.describe_volumes(
                                        VolumeIds = [
                                            created_volume['VolumeId']
                                        ])
                    if check_volume_status['Volumes'][0]['State'] == 'in-use':
                        print(check_volume_status['Volumes'][0]['VolumeId'], 'attached!')
                        break
                    else:
                        print(check_volume_status['Volumes'][0]['VolumeId'], 'is still', check_volume_status['Volumes'][0]['State'])
                        sleep(2)

        print('\nSuccessfully replaced', device['Ebs']['VolumeId'], 'with newly created', created_volume['VolumeId'])


print('\n=== Latest block device mapping ===')
for device in ec2_instance.block_device_mappings:
    print(device['DeviceName'], device['Ebs']['VolumeId'])

print('\n=== Latest volume status ===')
for volume in ec2_instance.volumes.all():
    print(volume.volume_id, ', fast_restored =', volume.fast_restored, ', size =', volume.size, ', state =', volume.state)


'''
Example result

===== Checking i-abcd1234 =====
us-west-2c
/dev/xvda vol-aaa
/dev/sdb vol-ccc
snap-bbb 100% vol-ccc 1024 12:06:22
snap-bbb FSR enabled with OptimizingTime 12:07:34 and EnabledTime 13:04:34
snap-ddd 100% vol-aaa 32 12:06:21
snap-ddd FSR enabled with OptimizingTime 12:06:38 and EnabledTime 12:08:21

Moving on to create the volumes? (Y/N)
Y

===== i-abcd1234 - stopped =====
=== Current block device mapping ===
/dev/xvda vol-aaa
/dev/sdb vol-ccc

About to replace vol-aaa on /dev/xvda
Moving on? (Y/N)
Y
snap-ddd is taken from vol-aaa

Creating a volume based on the snapshot.
vol-eee is still creating
vol-eee is still creating
vol-eee is still creating
vol-eee is still creating
vol-eee created!

Detaching volume vol-aaa
vol-aaa is still in-use
vol-aaa detached!

Attaching volume vol-eee
vol-eee attached!

About to replace vol-ccc on /dev/sdb
Moving on? (Y/N)
Y
snap-bbb is taken from vol-ccc

Creating a volume based on the snapshot.
vol-fff is still creating
vol-fff is still creating
vol-fff is still creating
vol-fff is still creating
vol-fff is still creating
vol-fff is still creating
vol-fff is still creating
vol-fff is still creating
vol-fff is still creating
vol-fff is still creating
vol-fff created!

Detaching volume vol-ccc
vol-ccc is still in-use
vol-ccc detached!

Attaching volume vol-fff
vol-fff attached!

=== Latest block device mapping ===
/dev/xvda vol-eee
/dev/sdb vol-fff

=== Latest volume status ===
vol-eee , fast_restored = True , size = 32 , state = in-use
vol-fff , fast_restored = True , size = 1024 , state = in-use
'''