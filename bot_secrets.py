import json
import boto3


class Secrets_Manager:

	def get_secret_dict():
		region_name = 'us-east-2'
		session = boto3.session.Session()
		client = session.client(service_name='secretsmanager', region_name=region_name)

		get_secret_value_response = client.get_secret_value(SecretId='bot_secrets')
		secret_dict = json.loads(get_secret_value_response['SecretString'])
		return secret_dict

	
	def get_openai_key():
		secret_dict = Secrets_Manager.get_secret_dict()
		return secret_dict['OPENAI_API_KEY_1']

	def get_omega_token():
		secret_dict = Secrets_Manager.get_secret_dict()
		return secret_dict['OMEGA_DISCORD_TOKEN']