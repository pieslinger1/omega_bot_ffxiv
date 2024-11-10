import os
import sys
import discord
import asyncio
from discord.ext import commands, tasks
from discord.ext.commands.errors import CommandNotFound
from discord import app_commands
from bot_loggers import bot_loggers
from bot_secrets import Secrets_Manager
from models import SwissTournament
from models import Team
import bot
import traceback
import utils
import constants
from db_io import DB_IO
from exceptions import DBItemRetrievalException

key = os.getenv('key')
wkey = os.getenv('wkey')

COMMAND_PREFIX = '-'

my_bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=discord.Intents.all())
my_bot.remove_command('help')

@my_bot.event
async def on_ready():
	# start loops
	start_loops()

	synced = await my_bot.tree.sync()
	bot_loggers.info_log("Synced " + str(len(synced)) + " commands: " + str(synced))
	bot_loggers.info_log("Started up Omega in deployment!")

def start_loops():
	pass

def handle_exception(exc_type, exc_value, exc_traceback):
	if issubclass(exc_type, KeyboardInterrupt):
		bot_loggers.info_log("Keyboard Interrupted")
		sys.__excepthook__(exc_type, exc_value, exc_traceback)
		return
	# Use traceback.format_exception to get the traceback as a string
	formatted_traceback = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))

	bot_loggers.err_log(f"Unhandled exception that got hooked:\nType: {exc_type}\nValue: {exc_value}\nTraceback:\n{formatted_traceback}")

sys.excepthook = handle_exception

@my_bot.event
async def on_raw_reaction_add(payload):
  await message_reaction_detected(payload, True)
  
@my_bot.event
async def on_raw_reaction_remove(payload):
  await message_reaction_detected(payload, False)

async def message_reaction_detected(payload, reaction_add):
	reaction_listen_channels = [
		constants.OMEGA_TEST_MAMMET_LABS_CHANNEL_ID
	]
	if not (payload.channel_id in reaction_listen_channels):
		return

	reaction_user_id = str(payload.user_id)
	if reaction_user_id == "1250630902732685455": # do nothing if it's Omega's reaction
		return

	bot_loggers.info_log("Heard a reaction on " + str(payload.message_id) + " reaction_add " + str(reaction_add) + " by " + str(payload.user_id) + " channel: " + str(payload.channel_id))


	reaction_guild = my_bot.get_guild(payload.guild_id)
	reaction_channel = reaction_guild.get_channel_or_thread(payload.channel_id)
	reaction_message = await reaction_channel.fetch_message(payload.message_id)
	reaction_emoji = payload.emoji

	await bot.process_reaction(my_bot, reaction_message, reaction_user_id, reaction_emoji, reaction_add)


@my_bot.command(name="ping")
async def ping(ctx):
	bot_loggers.info_log("ping from " + str(ctx.author.id))
	await ctx.send("pong!")


@my_bot.tree.command(name = "ping_omega", description = "Ping the Omega Bot")
async def ping_omega(interaction: discord.Interaction):
	await interaction.response.send_message("pong!")

@my_bot.tree.command(name = "create_swiss_tournament", description = "Create a new tournament with a Swiss format.")
@app_commands.describe(tournament_name = "The name of the tournament")
@app_commands.describe(max_rounds = "The maximum number of rounds in the Swiss format (3 by default)")
async def create_swiss_tournament(interaction: discord.Interaction, tournament_name: str, max_rounds: int = 3):
	await interaction.response.defer(thinking=True)
	new_tourney_id = utils.generate_random_id_string()
	new_tourney = SwissTournament(new_tourney_id, tournament_name, max_rounds)
	try:
		DB_IO.write_tournament_row(new_tourney.to_dict(), new_tourney_id)
		await interaction.followup.send("Created tournament named " + tournament_name + " and id " + new_tourney_id)
	except Exception as e:
		bot_loggers.err_log("Got unexpected exception " + str(e) + " for creating tournament " + tournament_name + " stack trace " + traceback.format_exc())
		await interaction.followup.send("Unexpected error. Pinging <@393301005682475016> to check on this issue.")


async def get_tournament_dict_from_id_or_interaction_report_failure(interaction, tournament_id):
	try:
		tournament_dict = DB_IO.load_tournament_row(tournament_id)
		if tournament_dict is None:
			await interaction.followup.send("There is no tournament with the ID " + tournament_id)
		else:
			return tournament_dict
	except DBItemRetrievalException as db_e:
		bot_loggers.err_log("Got item retreival exception " + str(db_e) + " when trying to fetch tournament ID " + str(tournament_id) + " stack trace " + traceback.format_exc())
		await interaction.followup.send("That request returned an unexpected error. Pinging <@393301005682475016> to check on this issue.")
		return None

@my_bot.tree.command(name = "register_team", description = "Create and register a team for an existing tournament. Only the captain should do this.")
@app_commands.describe(tournament_id = "The ID of the tournament you're creating a team for")
@app_commands.describe(team_name = "The name of your team (currently this cannot be edited later).")
async def register_team(interaction: discord.Interaction, tournament_id: str, team_name: str):
	await interaction.response.defer(thinking=True)
	new_team_id = utils.generate_random_id_string()
	team_captain_id = str(interaction.user.id)
	new_team = Team(new_team_id, team_name, team_captain_id, 0)
	
	joining_tournament_dict = await get_tournament_dict_from_id_or_interaction_report_failure(interaction, tournament_id)
	if joining_tournament_dict is None:
		return
	# For now, assuming swiss
	joining_tournament = SwissTournament.from_dict(joining_tournament_dict)
	if joining_tournament.signup_open:
		joining_tournament.add_team(new_team)
		DB_IO.write_tournament_row(joining_tournament.to_dict(), joining_tournament.tournament_id)
		await interaction.followup.send("Created team named \"" + team_name + "\" with team ID " + str(new_team_id) + " and team captain <@" + team_captain_id + "> for tournament named \"" + joining_tournament.tournament_name + "\" with tournament id " + joining_tournament.tournament_id)
	else:
		await interaction.followup.send("The tournament \"" + joining_tournament.tournament_name + "\" with ID " + joining_tournament.tournament_id + " has already begun, and signups are closed")

@my_bot.tree.command(name = "start_tournament", description = "Start a tournament, closing signups")
@app_commands.describe(tournament_id = "The ID of the tournament to start")
async def start_tournament(interaction: discord.Interaction, tournament_id: str):
	await interaction.response.defer(thinking=True)
	starting_tournament_dict = await get_tournament_dict_from_id_or_interaction_report_failure(interaction, tournament_id)
	if starting_tournament_dict is None:
		bot_loggers.warn_log("Got None starting tournament dict, check logs")
		return
	starting_tournament = SwissTournament.from_dict(starting_tournament_dict)
	bot_loggers.info_log("Got and starting tournament from dict " + str(starting_tournament_dict))

	if starting_tournament.round_index > -1:
		await interaction.followup.send("That tournament has already begun. Taking no action.", ephemeral = True)
	elif len(starting_tournament.team_dict.keys()) % 2 == 1:
		await interaction.followup.send("Can't start that tournament, it has an odd number of teams signed up! (" + str(len(starting_tournament.team_dict.keys())) + ")")
	else:

		(round_transition_code, round_transition_result) = starting_tournament.run_round_transition_pipeline()
		starting_tournament.signup_open = False
		if round_transition_code == 0:
			await interaction.followup.send("Started round " + str(starting_tournament.round_index + 1))
			send_channel = interaction.channel
			for matchup_arr in round_transition_result:
				send_content = await bot.generate_matchup_message_content(matchup_arr[0], matchup_arr[1], starting_tournament)
				sent_message = await send_channel.send(send_content)

				sun_fc_guild = my_bot.get_guild(constants.SUN_FC_GUILD_ID)
				team_1_emote = await sun_fc_guild.fetch_emoji(constants.TEAM_1_EMOTE_ID)
				team_2_emote = await sun_fc_guild.fetch_emoji(constants.TEAM_2_EMOTE_ID)
				await sent_message.add_reaction(team_1_emote)
				await sent_message.add_reaction(team_2_emote)

				message_listener_data = {
					"type" : "swiss_matchup_report_and_result_message",
					"tournament_id" : starting_tournament.tournament_id,
					"round_index" : starting_tournament.round_index, 
					"team_1_id" : matchup_arr[0],
					"team_2_id" : matchup_arr[1],
					"team_1_reported_result" : 0,
					"team_2_reported_result" : 0
				}
				DB_IO.write_listening_object(message_listener_data, str(sent_message.id))

		else:
			await interaction.followup.send("Reached the end of the tournament! Results are " + str(starting_tournament.get_team_and_points_dict()))
		DB_IO.write_tournament_row(starting_tournament.to_dict(), starting_tournament.tournament_id)


@my_bot.tree.command(name = "tournament_status", description = "DEV ONLY get status of a tournament")
@app_commands.describe(tournament_id = "The ID of the tournament to get status")
async def tournament_status(interaction: discord.Interaction, tournament_id: str):
	await interaction.response.defer(thinking=True)
	status_tournament_dict = await get_tournament_dict_from_id_or_interaction_report_failure(interaction, tournament_id)
	if status_tournament_dict is None:
		bot_loggers.warn_log("Got None starting tournament dict, check logs")
		return

	status_tournament = SwissTournament.from_dict(status_tournament_dict)
	points_dict = status_tournament.get_team_and_points_dict()

	status_string = "Tournament name " + str(status_tournament.tournament_name) + " id " + str(status_tournament.tournament_id) + " on round " + str(status_tournament.round_index + 1) + " Teams:"
	for team_id in points_dict:
		team_obj = status_tournament.team_dict[team_id]
		status_string += "\nTeam " + str(team_obj.team_name) + " (" + str(team_obj.team_id) + ") and captain <@" + str(team_obj.team_captain) + "> has " + str(points_dict[team_id]) + " points."
	
	await interaction.followup.send(status_string)
	bot_loggers.info_log(str(status_tournament_dict))

#@my_bot.tree.command(name = "report_match_result", description = "DEV COMMAND report the result of a match")
@app_commands.describe(tournament_id = "The ID of the tournament the match is for")
@app_commands.describe(winning_team_id = "The ID of the team that won")
@app_commands.describe(losing_team_id = "The ID of the team that lost")
async def report_match_result(interaction: discord.Interaction, tournament_id: str, winning_team_id: str, losing_team_id: str):
	await interaction.response.defer(thinking=True)
	reporting_tournament_dict = await get_tournament_dict_from_id_or_interaction_report_failure(interaction, tournament_id)
	if reporting_tournament_dict is None:
		bot_loggers.warn_log("Got None report match result tournament dict, check logs")
		return
	reporting_tournament = SwissTournament.from_dict(reporting_tournament_dict)
	bot_loggers.info_log("Got reporting tournament from dict " + str(reporting_tournament_dict))

	report_result = reporting_tournament.register_match_result(winning_team_id, losing_team_id, 0)
	DB_IO.write_tournament_row(reporting_tournament.to_dict(), reporting_tournament.tournament_id)
	if report_result == 0:
		await interaction.followup.send("Match result recorded.")
	if report_result == 1:
		await interaction.followup.send("Match result rejected. That matchup does not exist in the current round of the tournament.")

@my_bot.tree.command(name = "try_to_progress_tournament", description = "DEV COMMAND try to advance the tournament rounds, should be automatic in prod")
@app_commands.describe(tournament_id = "The ID of the tournament to check and try to progress")
async def try_to_progress_tournament(interaction: discord.Interaction, tournament_id: str):
	await interaction.response.defer(thinking=True)

	progress_tournament_dict = await get_tournament_dict_from_id_or_interaction_report_failure(interaction, tournament_id)
	if progress_tournament_dict is None:
		bot_loggers.warn_log("Got None reporting tournament dict, check logs")
		return
	progress_tournament = SwissTournament.from_dict(progress_tournament_dict)
	progress_channel = interaction.channel

	progress_result = await bot.try_to_progress_tournament(my_bot, progress_tournament, progress_channel)

	# TODO interaction follow up with progress_result code
	await interaction.followup.send("Done")




my_secret = Secrets_Manager.get_omega_token()

my_bot.run(my_secret)