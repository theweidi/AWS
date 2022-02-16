#!/usr/bin/env python3
from time import sleep
import boto3

INSTANCES = ['i-abcd1234', 'i-abcd5678']
AWS_REGION = 'us-west-2'

ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
ec2_client = boto3.client('ec2', region_name=AWS_REGION)

# List all specified instances 
ec2_instances = ec2_resource.instances.filter(
    InstanceIds=INSTANCES
)

# Get the current block device mappings
for instance in ec2_instances:

    print('\n===== Checking', instance.id, '=====')

    az = instance.placement['AvailabilityZone']
    print(instance.placement['AvailabilityZone'])

    for device in instance.block_device_mappings:
        print(device['DeviceName'], device['Ebs']['VolumeId'])

    # Describe snapshot status for this instance 

    snapshots = ec2_resource.snapshots.filter(
        Filters=[
            {
                'Name': 'tag:instance',
                'Values': [
                    instance.id
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
                print(snapshot.id, 'FSR is enabled with OptimizingTime', fsr_status['FastSnapshotRestores'][0]['OptimizingTime'].strftime("%H:%M:%S"),
                    'and EnabledTime', fsr_status['FastSnapshotRestores'][0]['EnabledTime'].strftime("%H:%M:%S"))
            else:
                print(snapshot.id, 'FSR is in', fsr_status['FastSnapshotRestores'][0]['State'], 'state')
        else:
            print('FSR might not be enabled.')


'''
Example result

===== Checking i-abcd5678 =====
us-west-2a
/dev/xvda vol-aaa
snap-aaa 100% vol-aaa 8 12:06:19
snap-aaa FSR is enabled with OptimizingTime 12:06:37 and EnabledTime 12:07:03

===== Checking i-abcd1234 =====
us-west-2c
/dev/xvda vol-bbb
/dev/sdb vol-ccc
snap-bbb 100% vol-bbb 1024 12:06:22
snap-bbb FSR is in enabling state
snap-ccc 100% vol-ccc 32 12:06:21
snap-ccc FSR is enabled with OptimizingTime 00:29:37 and EnabledTime 00:34:30
'''
