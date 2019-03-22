import os
import json
import time
from zipfile import ZipFile
import argparse
import boto3


def deploy_bot(key_name='github-bot-key',
               queue_name='github-bot-queue',
               lambda_name='github-bot-lambda',
               role_name_lambda='github-bot-lambda-role',
               role_name_ec2='github-bot-ec2-role'):

    print('Starting deployment process.')
    user_data = open('/'.join(os.path.realpath(__file__).split('/')[:-1]) + '/ec2-script.sh').read()
    roles_for_lambda = ['arn:aws:iam::aws:policy/AmazonSQSFullAccess',
                        'arn:aws:iam::aws:policy/AmazonEC2FullAccess',
                        'arn:aws:iam::aws:policy/AWSLambdaExecute']
    roles_for_ec2 = ['arn:aws:iam::aws:policy/AmazonSQSFullAccess',
                     'arn:aws:iam::aws:policy/service-role/AmazonEC2RoleforSSM']
    ssm_parameters = {
        'QUEUE_NAME': queue_name,
        'SHUTDOWN_TIME': '60',
        'GITHUB_TOKEN_FOR_BOT': os.getenv('GITHUB_TOKEN_FOR_BOT')
    }

    create_sqs(queue_name)
    print('SQS queue {} created'.format(queue_name))

    create_key_pair_for_ec2(key_name)
    print('Key pair for EC2 {} created'.format(key_name))

    ssm_response = create_ssm_parameters(ssm_parameters)
    for name in ssm_parameters:
        print('SSM parameter {} created'.format(name))

    iam_response = create_role(role_name_ec2, 'ec2.amazonaws.com', roles_for_ec2)
    role_arn = iam_response['Role']['Arn']
    print('IAM role {} created'.format(role_name_ec2))

    ec2_response = create_ec2_instance(role_name_ec2, key_name, user_data)
    instance_id = ec2_response['Instances'][0]['InstanceId']
    print('EC2 instance (id: {}) created'.format(instance_id))

    iam_response = create_role(role_name_lambda, 'lambda.amazonaws.com', roles_for_lambda)
    role_arn = iam_response['Role']['Arn']
    print('IAM role {} created'.format(role_name_lambda))

    time.sleep(10)

    lambda_response = create_lambda_function(role_arn, lambda_name, instance_id, queue_name)
    print('Lambda function {} created'.format(lambda_name))

    print('Deployment process succeeded.')


def create_ec2_instance(instance_role, key_name, user_data):
    ec2_client = boto3.client('ec2')
    response = ec2_client.run_instances(
        BlockDeviceMappings=[
            {
                'DeviceName': '/dev/xvda',
                'Ebs': {

                    'DeleteOnTermination': True,
                    'VolumeSize': 8,
                    'VolumeType': 'gp2'
                },
            },
        ],
        KeyName=key_name,
        UserData=user_data,
        ImageId='ami-0cd3dfa4e37921605',
        InstanceType='t2.micro',
        MaxCount=1,
        MinCount=1,
        Monitoring={
            'Enabled': False
        },
        SecurityGroupIds=[
            'sg-00f3b71d4b6021b03',
        ]
    )
    return response


def create_ssm_parameters(ssm_parameters):
    ssm_client = boto3.client('ssm')
    for name in ssm_parameters:
        response = ssm_client.put_parameter(
            Name=name,
            Value=ssm_parameters[name],
            Type='SecureString',
            Overwrite=True
        )
    return response


def create_key_pair_for_ec2(key_name):
    ec2_client = boto3.client('ec2')
    response = ec2_client.create_key_pair(KeyName=key_name)

    path_to_key = '{}{}.pem'.format('/'.join(os.path.realpath(__file__).split('/')[:-2]), key_name)

    with open(path_to_key, 'w') as key:
        key.write(response['KeyMaterial'])
    return response


def create_lambda_function(function_role, function_name, ec2_instance_id, queue_name):
    lambda_client = boto3.client('lambda')

    path_to_lambda = '/'.join(os.path.realpath(__file__).split('/')[:-2]) + '/lambda-function.py'
    zipf = ZipFile('lambda.zip', 'w')
    zipf.write(path_to_lambda, os.path.basename(path_to_lambda))
    zipf.close()

    with open('./lambda.zip', 'rb') as lambda_zip:
        lambda_code = lambda_zip.read()

    response = lambda_client.create_function(
        FunctionName=function_name,
        Runtime='python3.6',
        Role=function_role,
        Handler='lambda-function.handler',
        Code={'ZipFile': lambda_code},
        Environment={
            'Variables': {
                'INSTANCE_ID': ec2_instance_id,
                'QUEUE_NAME': queue_name
            }
        }
    )
    # TODO: connect api gateway to lambda
    '''lambda_client.add_permission(
        FunctionName=function_name,
        StatementId=function_name + "-ID",
        Action="lambda:InvokeFunction",
        Principal="apigateway.amazonaws.com",
        SourceArn="arn:aws:execute-api:" + self.region + ":" + self.getAccountId() + ":" + apiId + "/*/" + httpMethod + "/" + httpPath,
        # SourceAccount='string',
        # Qualifier='string'

    )'''
    os.remove('lambda.zip')
    return response


def create_role(role_name, service, role_policies):
    iam_client = boto3.client('iam')

    assume_role_policy_document = json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": service
                },
                "Action": "sts:AssumeRole"
            }
        ]
    })

    response = iam_client.create_role(
        Path='/service-role/',
        RoleName=role_name,
        AssumeRolePolicyDocument=assume_role_policy_document
    )
    for policy in role_policies:
        iam_client.attach_role_policy(
            RoleName=response['Role']['RoleName'],
            PolicyArn=policy
        )
    return response


def create_api_gateway(function_name):
    apigateway_client = boto3.client('apigateway')
    # TODO: create api gateway


def create_sqs(queue_name):
    sqs_client = boto3.client('sqs')
    response = sqs_client.create_queue(
        QueueName=queue_name
    )
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--github_token",
                        help="Token from github account. If token not specified, it"
                             " will be taken from MERGE_BOT_GITHUB_TOKEN environmental variable",
                        default=os.getenv("MERGE_BOT_GITHUB_TOKEN"))
    parser.add_argument("key_name",
                        help="Name of a key in ec2 key pair to be created. Default value is \"github-bot-key\"",
                        default="github-bot-key")
    parser.add_argument("queue_name",
                        help="Name of a queue to be created in SQS . Default value is \"github-bot-queue\"",
                        default="github-bot-queue")
    parser.add_argument("lambda_name",
                        help="Name of a Lambda function to be created. Default value is \"ggithub-bot-lambda\"",
                        default="github-bot-lambda")
    parser.add_argument("role_name_lambda",
                        help="Name of a role to be created for Lambda . Default value is \"github-bot-lambda-role\"",
                        default="github-bot-lambda-role")
    parser.add_argument("role_name_ec2",
                        help="Name of a role to be created for EC2 . Default value is \"github-bot-ec2-role\"",
                        default="github-bot-ec2-role")

    args = parser.parse_args()

    deploy_bot(args.github_token,
               key_name=args.key_name,
               queue_name=args.queue_name,
               lambda_name=args.lambda_name,
               role_name_lambda=args.role_name_lambda,
               role_name_ec2=args.role_name_ec2)


if __name__ == "__main__":
    main()
