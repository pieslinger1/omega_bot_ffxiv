import json
from bot_loggers import bot_loggers
import boto3
from exceptions import DBItemRetrievalException

# Initialize a DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
ddb_tournament_table = dynamodb.Table('OmegaTournamentDB')
ddb_listening_objects_table = dynamodb.Table('OmegaListeningDB')
s3 = boto3.resource('s3')


class DB_IO:

	def load_tournament_row(tournament_key):
		try:
			db_item = ddb_tournament_table.get_item(Key={'tournament_key': tournament_key})
			if 'Item' in db_item:
				return db_item['Item']['data']
			else:
				return None
		except Exception as e:
			raise DBItemRetrievalException("When getting a tournament key " + tournament_key + " got error " + str(e))

	def write_tournament_row(tournament_json, tournament_key):
		ddb_tournament_table.put_item(Item = {'tournament_key' : tournament_key, 'data' : tournament_json})


	def load_listening_object(discord_object_id):
		try:
			response = ddb_listening_objects_table.get_item(
				Key={
					'discord_object_id': str(discord_object_id)
				}
			)
			# Check if the item exists in the response
			if 'Item' in response:
				return response['Item']['data']
			else:
				return None
		except Exception as e:
			raise DBItemRetrievalException("When getting a discord_object_id key " + str(discord_object_id) + " got error " + str(e))

	def write_listening_object(object_data_json, discord_object_id):
		ddb_listening_objects_table.put_item(Item = {'discord_object_id' : str(discord_object_id), 'data' : object_data_json})

	def remove_listening_object(discord_object_id):
		try:
			response = ddb_listening_objects_table.delete_item(
				Key={
					'discord_object_id': discord_object_id
				}
			)
			return response
		except ClientError as e:
			bot_loggers.err_log(e.response['Error']['Message'])
			raise DBItemRetrievalException("When deleting a discord_object_id key " + str(discord_object_id) + " got error " + str(e))