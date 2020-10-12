import spotipy, json, sys, datetime, os, slack, logging
from spotipy.oauth2 import SpotifyOAuth
from pygments import highlight
from pygments.lexers import JsonLexer
from pygments.formatters import TerminalFormatter
from utils import *

device = os.environ.get("AUTHORED_DEVICE")

username = os.environ.get("USERNAME")
redirect_uri = "http://localhost:60680"

scope = "user-read-playback-state,user-modify-playback-state,user-read-currently-playing,streaming,app-remote-control,playlist-read-collaborative,playlist-modify-public,playlist-read-private,playlist-modify-private,user-library-modify,user-library-read,user-read-playback-position"

class spotibot:
	def __init__(self):
		self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
			scope=scope,
			username=username,
			redirect_uri=redirect_uri
		))
		self.current_user = self.sp.current_user()
		logging.info("Welcome to SpotiBot {} ✅".format(self.current_user['display_name']))
		self.bot_token = os.environ.get('SLACK_TOKEN')
		self.bot = slack.RTMClient(token=self.bot_token)
		self.client = slack.WebClient(self.bot_token)
		self.slack_id = os.environ.get('SLACK_ID')
		self.private_channel = os.environ.get("SLACK_CHANNEL").split(',')
		self.ensure_slack()
		slack.RTMClient.run_on(event='message')(self.run)
		self.bot.start()

	def ensure_slack(self):
		self.bot_info = self.client.api_call("auth.test")
		if self.bot_info.get("ok") is True:
			print("Connection succed\n",
				"{} : {}\n".format(yellow('team'), blue(self.bot_info['team'])),
				"{} : {}\n".format(yellow('user'), blue(self.bot_info['user'])))
		else:
			print("Connection failed\nRetry...")
			self.__init__()
	
	def parse_line(self, line):
		args = self.line[1:].strip().split(' ')
		self.cmd = args[0].lower()
		self.args = args[1:]
	
	def get_device(self):
		self.devices = self.sp.devices()
		for ldevice in self.devices['devices']:
			if ldevice['id'] == device:
				self.device = ldevice
				return ldevice
		self.device = None
		return None
	
	def prepare(self):
		self.current = self.sp.current_playback()
		self.get_device()
		self.available = (not self.current or self.current['is_playing'] == False or self.current['device']['id'] == device) and self.device != None

	def is_for_me(self):
		if self.data["text"] and self.data["blocks"][0]["elements"][0]["elements"][0]["text"]: self.line = " ".join(self.data["blocks"][0]["elements"][0]["elements"][0]["text"].split())
		if (not (self.data.get("bot_id")) and
			self.data["text"] and
			self.line[0] == "?" and
			self.data["channel"] in self.private_channel): #and
			#event.get("user") in self.allowed_users):
			return True
		else:
			return False
	
	def ensure_available(self, active=False):
		if not self.available:
			if self.device:	self.output("Spotify already on road :(")
			else:			self.output("Device is offline")
		elif active and not self.current:
			self.output("Device is not active, you must `?active` or `?play` before anything")
		return self.available and (not active or self.current)
	
	def output(self, message, as_json=False):
#		if as_json:
#			print(highlight(json.dumps(message, indent=4), JsonLexer(), TerminalFormatter()))
#		else:
#			print(message)
		self.client.chat_postMessage(
			channel=self.data["channel"],
			text=message,
			as_user=True,
		)
	
	def get_type(self, uri):
		try:
			self.sp.track(uri)
			return "track"
		except:
			pass
		try:
			self.sp.playlist(uri)
			return "playlist"
		except:
			pass
		try:
			self.sp.album(uri)
			return "album"
		except:
			pass
		try:
			self.sp.artist(uri)
			return "artist"
		except:
			pass
		return "none"
	
	def get_time(self, millis):
		millis = int(millis)
		seconds=(millis/1000)%60
		seconds = int(seconds)
		minutes=(millis/(1000*60))%60
		minutes = int(minutes)
		hours=(millis/(1000*60*60))%24
		hours = int(hours)
		output = ""
		if hours > 0:
			output += str(hours) + "h"
		if hours > 0 or minutes > 0:
			output += ("0" if minutes < 10 and hours > 0 else "") + str(minutes) + "m"
		if hours > 0 or minutes > 0 or seconds > 0:
			output += ("0" if seconds < 10 and (hours > 0 or minutes > 0) else "") + str(seconds) + "s"
		return output
	
	def remove_market(self, d):
		if not isinstance(d, (dict, list)):
			return d
		if isinstance(d, list):
			return [self.remove_market(v) for v in d]
		return {k: self.remove_market(v) for k, v in d.items()
				if k not in {'available_markets'}}

	def get_info(self):
		for arg in self.args:
			uritype = self.get_type(arg)
			if uritype == "none":
				self.output("Unknown URI, format is `spotify:TYPE:ID`")
			else:
				self.info = getattr(self.sp, uritype)(arg)
				self.output("Name: {}\n URI: `{}`\nType: {}\n".format(self.info['name'], arg, uritype))
	
	def get_current(self):
		if self.ensure_available(True):
			output = []
			output.append("Playing: {}".format(self.current['is_playing']))
			if self.current['is_playing']:
				output.append("- Title: {}".format(self.current['item']['name']))
				artists = []
				for artist in self.current['item']['artists']:
					artists.append("<{}|{}>".format(artist['external_urls']['spotify'], artist['name']))
				output.append("- Artist: {}".format(", ".join(artists)))
				output.append("- Album: <{}|{}> ({})".format(self.current['item']['album']['external_urls']['spotify'], self.current['item']['album']['name'], self.current['item']['album']['release_date']))
				output.append("- Type: {}".format(self.current['item']['type']))
				output.append("- Duration: {} / {} ({}%)".format(self.get_time(self.current['progress_ms']), self.get_time(self.current['item']['duration_ms']), int(100 * int(self.current['progress_ms']) / int(self.current['item']['duration_ms']))))
			if self.device['is_active']:
				output.append("Repeat: {}".format(self.current['repeat_state']))
				output.append("Shuffle: {}".format(self.current['shuffle_state']))
				output.append("Volume: {}".format(self.current['device']['volume_percent']))
			output.append("Active: {}".format(self.device['is_active']))
			self.output("\n".join(output))
	
	def play(self):
		if self.ensure_available():
			if len(self.args) == 0:
				if self.device and not self.device['is_active']:
					self.sp.transfer_playback(device)
				else:
					self.sp.start_playback()
			else:
				uritypes = dict()
				for arg in self.args:
					uritype = self.get_type(arg)
					if uritype not in uritypes:
						uritypes[uritype] = 0
					uritypes[uritype] += 1
				key = next(iter(uritypes))
				if len(uritypes) > 1:
					self.output("Cannot play different types of URI")
				elif key != "track" and uritypes[key] > 1:
					self.output("Cannot play different URI of that type")
				else:
					if key == "track":
						self.sp.start_playback(device_id=device,uris=self.args)
					elif key != "none":
						self.sp.start_playback(device_id=device,context_uri=self.args[0])
					self.get_info()

	def transfer(self):
		if self.ensure_available():
			if self.device and not self.device['is_active']:
				self.sp.transfer_playback(device, force_play=False)
				self.output("Device is now active")
			else:
				self.output("Device already active")
	
	def pause(self):
		if self.ensure_available(True):
			self.sp.pause_playback()
	
	def play_next(self):
		if self.ensure_available(True):
			self.sp.next_track()
	
	def play_prev(self):
		if self.ensure_available(True):
			self.sp.previous_track()

	def seek(self):
		if self.ensure_available(True):
			if len(self.args) != 1:
				self.output("You just need to pass seconds or seconds_delta")
			else:
				if self.args[0][0] in ["+", "-"]:
					timestamp = getattr(self.current['progress_ms'], ("__add__" if self.args[0][0] == "+" else "__sub__"))(int(self.args[0][1:]) * 1000)
				elif self.args[0].isdigit():
					timestamp = int(self.args[0]) * 1000
				else:
					self.output("Invalid time")
					return
				if timestamp < 0: timestamp = 0
				if timestamp > self.current['item']['duration_ms']:
					self.output("Out of range")
				else:
					self.sp.seek_track(timestamp)

	def set_repeat(self):
		if self.ensure_available(True):
			if len(self.args) == 0:
				self.output("Current repeat mode is `{}`".format(self.current['repeat_state']))
			elif len(self.args) > 1:
				self.output("Too many arguments")
			elif self.args[0].lower() not in ["track", "context", "off"]:
				self.output("Invalid repeat mode, use one of `track`, `context` & `off`")
			else:
				self.sp.repeat(self.args[0].lower())

	def set_shuffle(self):
		if self.ensure_available(True):
			if len(self.args) == 0:
				self.output("Shuffle is set on `{}`".format(self.current['shuffle_state']))
			elif len(self.args) > 1:
				self.output("Too many arguments")
			elif self.args[0].lower() not in ["true", "false"]:
				self.output("Invalid shuffle mode, use one of `true` & `false`")
			else:
				self.sp.shuffle(self.args[0].lower() in ["true"])

	def set_volume(self):
		if self.ensure_available(True):
			if len(self.args) == 0:
				self.output("Actual volume is `{}`".format(self.current['device']['volume_percent']))
			elif len(self.args) > 1:
				self.output("Too many arguments")
			elif not self.args[0].isdigit() or int(self.args[0]) > 100:
				self.output("Invalid volume, enter an integer between `0` & `100`")
			else:
				self.sp.volume(int(self.args[0]))
	
	def search(self):
		output = []
		for typekey in ["track", "artist", "album", "playlist"]:
			result = self.sp.search(q=" ".join(self.args),type=typekey)
			typekey += "s"
			output.append("{}: {} result(s)".format(typekey, result[typekey]['total']))
			for item in result[typekey]['items']:
				infos = []
				if typekey in ["tracks", "albums"]:
					for artist in item['artists']:
						infos.append(artist['name'])
				elif typekey == "playlists":
					infos.append(item['owner']['display_name'])
					infos.append("{} songs".format(item['tracks']['total']))
				elif typekey == "artists":
					for genre in item['genres']:
						infos.append(genre)
				output.append("{} - {} | `{}`".format(item['name'], ", ".join(infos), item["uri"]))
			output.append("")
		self.output("\n".join(output))

	def show_favorite(self):
		self.playlist = self.sp.user_playlist_tracks(playlist_id="spotify:playlist:1pFPQgP11MBk6LLWhsMaWb")
		self.output("Total: {}".format(self.playlist['total']))
		for track in self.playlist['items']:
			self.output("<{}|{}> - <preview|{}>".format(track['track']['name'], track['track']['href'], track['track']['preview_url']))
	
	def help(self):
		self.output("""
`  ?info  ` - Get info about an URI
`  ?play  ` - Resume or start another song
` ?active ` - Active device
`  ?next  ` - Next song
`  ?prev  ` - Previous song
`  ?seek  ` - Jump for [+|-]# seconds
` ?pause  ` - Pause song
`?current ` - Get infos about player
` ?repeat ` - Get or set repeat state
`?shuffle ` - Get or set shuffle state
` ?volume ` - Set Spotify volume
` ?search ` - Search for tracks, artists, albums & playlists
`?favorite` - Show favorites songs
`  ?help  ` - Display this help
		""")
	
	def dispatch(self):
		if   self.cmd == "info":		self.get_info()
		elif self.cmd == "play":		self.play()
		elif self.cmd == "active":		self.transfer()
		elif self.cmd == "prev":		self.play_prev()
		elif self.cmd == "next":		self.play_next()
		elif self.cmd == "seek":		self.seek()
		elif self.cmd == "pause":		self.pause()
		elif self.cmd == "current":		self.get_current()
		elif self.cmd == "repeat":		self.set_repeat()
		elif self.cmd == "shuffle":		self.set_shuffle()
		elif self.cmd == "volume":		self.set_volume()
		elif self.cmd == "search":		self.search()
		elif self.cmd == "favorite":	self.show_favorite()
		elif self.cmd == "help":		self.help()
	
	def run(self, **event):
		self.event = event
		self.data = self.event["data"]
		if self.is_for_me() == True:
			try:
				self.parse_line(self.line)
				self.prepare()
				self.dispatch()
			except Exception as e:
				logging.info(e)

if __name__ == "__main__":
	sp = spotibot()
