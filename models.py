from enum import Enum
from exceptions import FormatNotRecognizedException
from exceptions import ShouldNotBeHereException
from bot_loggers import bot_loggers
import utils

class Format(Enum):
	SWISS = "swiss"

class Discord_Object_Listerners_Types(Enum):
	swiss_matchup_report_and_result_message = "swiss_matchup_report_and_result_message"


'''
swiss_matchup_report_and_result_message data model
{
	"type" : "swiss_matchup_report_and_result_message",
	"tournament_id" : <string>,
	"round_index" : <string>, 
	"team_1_id" : <string>,
	"team_2_id" : <string>,
	"team_1_reported_result" : <0 for none yet, 1 for team 1 win, 2 for team 2 win>,
	"team_2_reported_result" : <0 for none yet, 1 for team 1 win, 2 for team 2 win>
}


'''

class Tournament:

	def __init__(self, tournament_id, tournament_name, tournament_format):
		self.team_dict = {}
		self.tournament_id = tournament_id
		self.tournament_name = tournament_name
		self.tournament_format = Format(tournament_format)
		self.active_status = False
		self.signup_open = True

	def add_team(self, team):
		# TODO validate team object
		self.team_dict[team.team_id] = team

	def to_dict(self):
		return {
			'tournament_id': self.tournament_id,
			'tournament_name': self.tournament_name,
			'tournament_format': self.tournament_format.value,
			'team_dict': {team_id: team.to_dict() for team_id, team in self.team_dict.items()},
			'active_status': self.active_status,
			'signup_open' : self.signup_open
		}

	@classmethod
	def from_dict(cls, data):
		tournament = cls(data['tournament_id'], data['tournament_name'], data['tournament_format'])
		tournament.team_dict = {team_id: Team.from_dict(team_data) for team_id, team_data in data['team_dict'].items()}
		tournament.active_status = data['active_status']
		tournament.signup_open = data['signup_open']
		return tournament

	def generate_next_round_matchups(self):
		raise ShouldNotBeHereException("This method should never be called")

class SwissTournament(Tournament):

	def __init__(self, tournament_id, tournament_name, max_rounds):
		super().__init__(tournament_id, tournament_name, Format.SWISS)
		self.round_index = -1
		self.max_rounds = max_rounds

		# array of arrays for match history
		# match_history[i] is for round i
		# match_history[i][j] is for match j
		# match_history[i][j][0] is team 0, match_history[i][j][1] is team 1, match_history[i][j][2] is -1 for no result yet, 0 for team 0, 1 for team 1 victory, 2 for tie/draw
		self.match_history = []

	def to_dict(self):
		super_dict = super().to_dict()
		super_dict['round_index'] = self.round_index
		super_dict['max_rounds'] = self.max_rounds
		super_dict['match_history'] = self.match_history
		return super_dict

	@classmethod
	def from_dict(cls, data):
		tournament = super(SwissTournament, cls).from_dict(data)
		tournament.round_index = int(data['round_index'])
		tournament.max_rounds = int(data['max_rounds'])
		tournament.match_history = data['match_history']
		return tournament

	def run_round_transition_pipeline(self):
		if self.round_index + 1 < self.max_rounds:
			self.round_index += 1
			next_round_matchups = self.generate_next_round_matchups()
			self.match_history.append(next_round_matchups)
			return (0, next_round_matchups) # code for moving on
		else:
			return (1, None) # code for tournament is over

	def current_round_is_complete(self):
		for match in self.match_history[self.round_index]:
			if match[2] == -1:
				return False
		return True

	def generate_next_round_matchups(self):
		#TODO logic for next round matchups
		points_counts = {}
		for team_id in self.team_dict.keys():
			points_counts[team_id] = 0

		matchup_counts = {}

		for round_matrix in self.match_history:
			for match_arr in round_matrix:
				winner_index = match_arr[2]
				if winner_index == 0 or winner_index == 1:
					points_counts[match_arr[int(winner_index)]] += 1
				elif winner_index == 2:
					points_counts[match_arr[0]] += 0.5
					points_counts[match_arr[1]] += 0.5
				else:
					raise ShouldNotBeHereException("Got a request for a next round matchup with invalid index in match: " + str(match_arr))

				match_key = utils.order_strings(match_arr[0], match_arr[1])
				if not match_key in matchup_counts:
					matchup_counts[match_key] = 0
				matchup_counts[match_key] += 1

		points_and_teams_arr = []
		for team_id in points_counts:
			points_and_teams_arr.append((points_counts[team_id], team_id))

		points_and_teams_arr.sort(reverse = True)
		bot_loggers.info_log("Tournament id " + str(self.tournament_id) + " round index " + str(self.round_index) + " got points_and_teams_arr " + str(points_and_teams_arr))
		matched_this_round = [False for i in range(len(points_and_teams_arr))]
		new_round_matchups = []

		while_limit = 333
		max_match_repeat_threshold = 0
		max_match_repeat_key = "MAX_DEFAULT"

		for i in range(len(points_and_teams_arr)):
			match_repeat_threshold = 0
			bot_loggers.info_log("in matchmaking, outside while, i = " + str(i))
			while (not matched_this_round[i]) and max_match_repeat_threshold < while_limit:
				bot_loggers.info_log("while condition: " + str((not matched_this_round[i]) and max_match_repeat_threshold < while_limit) + " first part: " + str((not matched_this_round[i])) + " second: " + str(max_match_repeat_threshold < while_limit))
				for j in range(i + 1, len(points_and_teams_arr)):
					bot_loggers.info_log("in matchmaking, i = " + str(i) + " j = " + str(j) + " matched_this_round " + str(matched_this_round))
					if matched_this_round[i] or matched_this_round[j]:
						continue
					(_, team_i_id) = points_and_teams_arr[i]
					(_, team_j_id) = points_and_teams_arr[j]
					match_key = utils.order_strings(team_i_id, team_j_id)
					if (not (match_key in matchup_counts)) or (matchup_counts[match_key] <= match_repeat_threshold):
						new_round_matchups.append([team_i_id, team_j_id, -1])
						matched_this_round[i] = True
						matched_this_round[j] = True
						bot_loggers.info_log("Matched " + str((i, team_i_id)) + " with " + str((j, team_j_id)) + " on threshold " + str(match_repeat_threshold))
						if match_repeat_threshold > max_match_repeat_threshold:
							max_match_repeat_threshold = match_repeat_threshold
							max_match_repeat_key = match_key

				match_repeat_threshold += 1

			bot_loggers.info_log("in matchmaking, after while")
			if match_repeat_threshold >= while_limit:
				raise ShouldNotBeHereException("It should not be possible to hit a match repeat of " + str(match_repeat_threshold) + " looking at history " + str(self.match_history) + " and currently on " + str(i) + " in " + str(points_and_teams_arr))

		bot_loggers.info_log("Have matchups " + str(new_round_matchups))
		return new_round_matchups

	def get_team_and_points_dict(self):
		points_counts = {}
		for team_id in self.team_dict.keys():
			points_counts[team_id] = 0

		bot_loggers.info_log("Getting points for team ids " + str(points_counts.keys()))

		for round_matrix in self.match_history:
			for match_arr in round_matrix:
				winner_index = match_arr[2]
				if winner_index == 0 or winner_index == 1:
					points_counts[match_arr[int(winner_index)]] += 1
				elif winner_index == 2:
					points_counts[match_arr[0]] += 0.5
					points_counts[match_arr[1]] += 0.5

		return points_counts

	def register_match_result(self, winning_team_id, losing_team_id, result_code):
		# result code should be 0 for win/loss 1 for draw
		match_found = False
		for match_num in range(len(self.match_history[self.round_index])):
			if self.match_history[self.round_index][match_num][0] == winning_team_id and self.match_history[self.round_index][match_num][1] == losing_team_id:
				self.match_history[self.round_index][match_num][2] = result_code * 2
				match_found = True
				break
			elif self.match_history[self.round_index][match_num][0] == losing_team_id and self.match_history[self.round_index][match_num][1] == winning_team_id:
				self.match_history[self.round_index][match_num][2] = result_code + 1
				match_found = True
				break
			else:
				continue
		if match_found:
			return 0 # success code
		return 1





class Team:

	def __init__(self, team_id, team_name, team_captain, team_seed):
		self.team_id = team_id
		self.team_name = team_name
		self.team_captain = team_captain
		self.team_seed = team_seed

	def to_dict(self):
		return {
			'team_id': self.team_id,
			'team_name': self.team_name,
			'team_captain': self.team_captain,
			'team_seed': self.team_seed
		}

	@classmethod
	def from_dict(cls, data):
		team = cls(data['team_id'], data['team_name'], data['team_captain'], data['team_seed'])
		return team