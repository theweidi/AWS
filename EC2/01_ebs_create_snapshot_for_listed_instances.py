#!/usr/bin/env python3
import boto3

INSTANCES = ['i-abcd5678', 'i-abcd1234']
AWS_REGION = 'us-west-2'

ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
ec2_client = boto3.client('ec2', region_name=AWS_REGION)

# List all specified instances 
ec2_instances = ec2_resource.instances.filter(
    InstanceIds=INSTANCES
)

for instance in ec2_instances:

    print('\n===== Checking', instance.id, '=====')

    # Get the current AZ to enable FSR
    az = instance.placement['AvailabilityZone']
    print(instance.placement['AvailabilityZone'])

    # Get the current block device mappings
    for device in instance.block_device_mappings:
        print(device['DeviceName'], device['Ebs']['VolumeId'])


    # Create a snapshot for all volumes 
    for volume in instance.volumes.all():
        snapshot = volume.create_snapshot(
            Description= 'for instance ' + instance.id,
            TagSpecifications=[
                {
                    'ResourceType': 'snapshot',
                    'Tags': [
                        {
                            'Key': 'instance',
                            'Value': instance.id
                        },
                    ]
                },
            ]
        )
        print('Snapshot', snapshot.id, 'is created for', snapshot.volume_id)
        enable_fsr = ec2_client.enable_fast_snapshot_restores(
            AvailabilityZones=[
                az
            ],
            SourceSnapshotIds=[
                snapshot.id
            ]
        )
        if enable_fsr['Successful']:
            print('Snapshot', snapshot.id, 'enabled FSR on', az)
        else:
            print('Something went wrong! Exiting...')
            break


'''

Example result
 
===== Checking i-abcd1234 =====
us-west-2a
/dev/xvda vol-xxx
Snapshot snap-yyy is created for vol-xxx
Snapshot snap-yyy enabled FSR on us-west-2a

===== Checking i-abcd5678 =====
us-west-2c
/dev/xvda vol-aaa
/dev/sdb vol-bbb
Snapshot snap-aaa is created for vol-aaa
Snapshot snap-aaa enabled FSR on us-west-2c
Snapshot snap-bbb is created for vol-bbb
Snapshot snap-bbb enabled FSR on us-west-2c

'''