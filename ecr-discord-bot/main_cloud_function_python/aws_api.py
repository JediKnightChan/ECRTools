import os
import boto3

class AWSWorker:
	def __init__(self):
		self.service = 'ec2'
		
		self.aws_user_key = os.getenv("AWS_USER_KEY", "")
		if not self.aws_user_key:
			raise ValueError("AWS_USER_KEY not set")
		
		self.aws_user_secret = os.getenv("AWS_USER_SECRET", "")
		if not self.aws_user_secret:
			raise ValueError ("AWS_USER_SECRET not set")
			
	def __get_connection(self, region):
		return boto3.client(self.service, 
				region_name = region, 
				aws_access_key_id = self.aws_user_key, 
				aws_secret_access_key = self.aws_user_secret)
	
	def start_instance(self, region, instance_id):
		ec2 = self.__get_connection(region)
		return ec2.start_instances(InstanceIds=[instance_id])
	
	def stop_instance(self, region, instance_id):
		ec2 = self.__get_connection(region)
		return ec2.stop_instances(InstanceIds=[instance_id])
