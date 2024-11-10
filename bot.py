from db_io import DB_IO
from bot_loggers import bot_loggers
from models import Discord_Object_Listerners_Types
from models import SwissTournament
import constants


async def process_reaction(my_bot, reaction_message, reaction_user_id, reaction_emoji, reaction_add):
	reaction_message_id = str(reaction_message.id)
	message_listening_object = DB_IO.load_listening_object(reaction_message_id)

	if message_listening_object is None:
		bot_loggers.info_log("Got reaction by " + str(reaction_user_id) + " on message id " + str(reaction_message_id) + " emoji " + str(reaction_emoji) + " channel " + str(reaction_message.channel.name))
		return

	match(message_listening_object['type']):
		case Discord_Object_Listerners_Types.swiss_matchup_report_and_result_message.value:
			return await process_swiss_matchup_report_and_result_message_reaction(my_bot, message_listening_object, reaction_message, reaction_user_id, reaction_emoji, reaction_add)
		case _:
			bot_loggers.err_log("Got unrecognized reaction type " + str(message_listening_object["type"]))
			raise DBItemRetrievalException("Got unrecognized reaction type " + str(message_listening_object["type"]))


async def process_swiss_matchup_report_and_result_message_reaction(my_bot, message_listening_object, reaction_message, reaction_user_id, reaction_emoji, reaction_add):
	tournament_dict = DB_IO.load_tournament_row(message_listening_object["tournament_id"])
	if tournament_dict is None:
		raise DBItemRetrievalException("Tournament with the id " + str(message_listening_object["tournament_id"]) + " does not exist, couldn't find it from message listening object " + str(message_listening_object))

	tournament = SwissTournament.from_dict(tournament_dict)

	# make sure its the current round

	if message_listening_object["round_index"] != tournament.round_index:
		bot_loggers.info_log("Got reaction on message " + str(reaction_message) + " with listening object " + str(message_listening_object) + " and round index " + str(message_listening_object["round_index"]) + " != " + str(tournament.round_index))
		return None


	team_1_id = message_listening_object["team_1_id"]
	team_2_id = message_listening_object["team_2_id"]

	# make sure the reaction came from one of the captains

	reaction_captain_key = None
	if reaction_user_id == tournament.team_dict[team_1_id].team_captain:
		reaction_captain_key = "team_1_reported_result"
	elif reaction_user_id == tournament.team_dict[team_2_id].team_captain:
		reaction_captain_key = "team_2_reported_result"
	else:
		bot_loggers.info_log("Reaction user id " + str(reaction_user_id) + " did not match captains " + str(tournament.team_dict[team_1_id].team_captain) + " or captain " + str(tournament.team_dict[team_2_id].team_captain))
		return None

	# based on the reaction emoji record in the message listening object that that team reported that result
	reaction_emoji_id = None
	if reaction_emoji.is_custom_emoji():
		reaction_emoji_id = reaction_emoji.id
	else:
		return 1 # TODO clean up return locations, formalize handling edge cases

	reporting_result = 0
	# blue will be team 1 because astra is blue
	if reaction_emoji_id == constants.TEAM_1_EMOTE_ID:
		reporting_result = 1
	elif reaction_emoji_id == constants.TEAM_2_EMOTE_ID:
		reporting_result = 2
	else:
		bot_loggers.info_log("Got reaction emoji " + str(reaction_emoji) + " which isn't recognized on message " + str(reaction_message) + " with listening object " + str(message_listening_object))
		return None

	bot_loggers.info_log("message_listening_object before update: " + str(message_listening_object))
	message_listening_object[reaction_captain_key] += reporting_result * (1 if reaction_add else -1)
	bot_loggers.info_log("message_listening_object after update: " + str(message_listening_object))
	reaction_message_id = str(reaction_message.id)
	DB_IO.write_listening_object(message_listening_object, reaction_message_id)

	# check if both teams reported a result and that they agree
	reporting_result = None
	if message_listening_object["team_1_reported_result"] == message_listening_object["team_2_reported_result"] and message_listening_object["team_1_reported_result"] > 0 and message_listening_object["team_1_reported_result"] < 3:
		winning_team_key = "team_" + str(message_listening_object["team_1_reported_result"]) + "_id"
		losing_team_key = "team_" + str(int(3 - message_listening_object["team_1_reported_result"])) + "_id"
		reporting_result = tournament.register_match_result(message_listening_object[winning_team_key], message_listening_object[losing_team_key], 0)
		DB_IO.write_tournament_row(tournament.to_dict(), tournament.tournament_id)

	# if the result was reported then the result needs to be recorded in the tournament object
	if reporting_result == 0: # success
		bot_loggers.info_log("Successfully recorded result for tournament " + str(message_listening_object["tournament_id"]) + " teams " + str(team_1_id) + " " + str(team_2_id) + " emoji " + str(reaction_emoji))
		DB_IO.remove_listening_object(str(reaction_message.id))
		message_existing_content = reaction_message.content
		await reaction_message.edit(content = message_existing_content + "\nResult recorded!")
		await try_to_progress_tournament(my_bot, tournament, reaction_message.channel)
		# TODO edit the message to say which result was recorded
		return 0
	elif reporting_result == 1: # match wasnt found
		bot_loggers.info_log("Match not found for result for tournament " + str(message_listening_object["tournament_id"]) + " teams " + str(team_1_id) + " " + str(team_2_id) + " round " + str(round_index))
		return 1


async def generate_matchup_message_content(team_1_id, team_2_id, tournament):
	team_1_captain_id = tournament.team_dict[team_1_id].team_captain
	team_1_name = tournament.team_dict[team_1_id].team_name
	team_2_captain_id = tournament.team_dict[team_2_id].team_captain
	team_2_name = tournament.team_dict[team_2_id].team_name

	points_dict = tournament.get_team_and_points_dict()

	content = "**Round " + str(tournament.round_index + 1) + " Matchup:**\n<:blue_square:1253909758885363732> **Team: " + team_1_name + "** (Captain <@" + team_1_captain_id + "> and score " + str(points_dict[team_1_id]) + ")\n<:red_triangle:1253909787931050056> **Team: " + team_2_name + "** (Captain <@" + team_2_captain_id + "> and score " + str(points_dict[team_2_id]) + ")"

	return content

	


async def try_to_progress_tournament(my_bot, progress_tournament, tournament_channel):
	if not progress_tournament.current_round_is_complete():
		bot_loggers.info_log("That current round is not yet complete")
	else:
		(round_transition_code, round_transition_result) = progress_tournament.run_round_transition_pipeline()
		progress_tournament.signup_open = False
		DB_IO.write_tournament_row(progress_tournament.to_dict(), progress_tournament.tournament_id)
		if round_transition_code == 0:
			await tournament_channel.send("Started round " + str(progress_tournament.round_index + 1))
			for matchup_arr in round_transition_result:
				send_content = await generate_matchup_message_content(matchup_arr[0], matchup_arr[1], progress_tournament)
				sent_message = await tournament_channel.send(send_content)

				sun_fc_guild = my_bot.get_guild(constants.SUN_FC_GUILD_ID)
				team_1_emote = await sun_fc_guild.fetch_emoji(constants.TEAM_1_EMOTE_ID)
				team_2_emote = await sun_fc_guild.fetch_emoji(constants.TEAM_2_EMOTE_ID)
				await sent_message.add_reaction(team_1_emote)
				await sent_message.add_reaction(team_2_emote)

				message_listener_data = {
					"type" : "swiss_matchup_report_and_result_message",
					"tournament_id" : progress_tournament.tournament_id,
					"round_index" : progress_tournament.round_index, 
					"team_1_id" : matchup_arr[0],
					"team_2_id" : matchup_arr[1],
					"team_1_reported_result" : 0,
					"team_2_reported_result" : 0
				}
				DB_IO.write_listening_object(message_listener_data, str(sent_message.id))

		else:
			await tournament_channel.send("Reached the end of the tournament! Results are " + str(progress_tournament.get_team_and_points_dict()))

