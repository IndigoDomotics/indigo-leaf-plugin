import yaml
import indigo
import logging
from datetime import datetime, timedelta
from pycarwings2.pycarwings2 import CarwingsError
from urllib2 import HTTPError

import pycarwings2

import distance_scale

DISTANCE_SCALE_MAP = {
	"k" : distance_scale.Kilometers(),
	"m" : distance_scale.Miles(),
	"f" : distance_scale.Furlongs()
}

log = logging.getLogger('indigo.nissanleaf.plugin')

def _timedelta_to_minutes(td):
	return (td.days * 24 * 60) + (td.seconds / 60)

def _timedelta_to_seconds(td):
	return (td.days * 24 * 60 * 60) + td.seconds

def _minutes_to_dms(x):
	if x == 0:
		return "0m"

	(days, mins) = divmod(x, 24 * 60)
	(hrs,  mins) = divmod(mins, 60)
	return ( (str(days) + "d" if (days > 0) else "") +
		     (str(hrs)  + "h" if (hrs  > 0) else "") +
		     (str(mins) + "m" if (mins > 0) else "") )

class IndigoLeaf:

	# class variables
	session = None
	distance_format = distance_scale.Miles()

	vins = []

	@staticmethod
	def setup(username, password, region):
		log.debug("indigoleaf setup; username: %s, region: %s" % (username, region))
		IndigoLeaf.session = pycarwings2.pycarwings2.Session(username, password, region)
		log.debug("indigoleaf session: %s" % IndigoLeaf.session)

	@staticmethod
	def use_distance_scale(s):
		log.debug("using distance scale '%s'" % s)
		IndigoLeaf.distance_format = DISTANCE_SCALE_MAP[s]

	def login(self):
		log.debug("logging in to carwings")
		IndigoLeaf.session.connect()
#		status = IndigoLeaf.userservice.login_and_get_status()
#		if IndigoLeaf.connection.logged_in:
#			vin = status.user_info.vin
#			log.info( "logged in, vin: %s, nickname: %s" % (vin, status.user_info.nickname))
#			IndigoLeaf.vins = [(vin, status.user_info.nickname)]
#		else:
#			log.error( "Log in invalid, please try again")
		l = IndigoLeaf.session.get_leaf()
		self.leaf = l
		IndigoLeaf.vins = [(l.vin, l.nickname)]
		log.info("logged in, vin: %s, nickname: %s" % (l.vin, l.nickname))
		log.debug("self.leaf is: %s" % self.leaf)

	@staticmethod
	def get_vins():
		return IndigoLeaf.vins

	def __init__(self, dev, plugin, charging_freq_min=15, not_charging_freq_min=15, error_freq_min=60):
		log.debug("IndigoLeaf object init")
		self.dev = dev
		self.leaf = None
		self.charging = False
		self.last_update_timestamp = datetime(2000, 1, 1)

		# default/initialization values only, overridden by subsequent call to set_update_frequencies
		self.charging_update_frequency_minutes=15
		self.not_charging_update_frequency_minutes=15
		self.error_update_frequency_minutes=60
		# overrides the three default values just above
		self.set_update_frequencies(charging_freq_min, not_charging_freq_min, error_freq_min)

		self.next_update_timestamp = datetime.now()


		log.debug("update frequencies:   charging: %d min, not charging: %d min" % (charging_freq_min, not_charging_freq_min) )

		if "address" in dev.pluginProps:
			# version 0.0.3
			self.vin = dev.pluginProps["address"]
		elif "vin" in dev.pluginProps:
			# version 0.0.1
			self.vin = dev.pluginProps["vin"]
		else:
			log.error("couldn't find a property with the VIN: %s" % dev.pluginProps)

	def set_update_frequencies(self, charging_freq_min, not_charging_freq_min, error_freq_min):
		self.charging_update_frequency_minutes=charging_freq_min
		self.not_charging_update_frequency_minutes = not_charging_freq_min
		self.error_update_frequency_minutes = error_freq_min


	def start_charging(self):
		if not self.leaf:
			self.login()
		try:
			self.leaf.start_charging()
		except pycarwings2.pycarwings2.CarwingsError as e:
			log.warn("error starting charging")
			raise e

	def start_climate_control(self):
		if not self.leaf:
			self.login()
		try:
			self.leaf.start_climate_control()
		except pycarwings2.pycarwings2.CarwingsError as e:
			log.warn("error starting climate control")
			raise e

	def stop_climate_control(self):
		if not self.leaf:
			self.login()
		try:
			self.leaf.stop_climate_control()
		except pycarwings2.pycarwings2.CarwingsError as e:
			log.warn("error stopping climate control")
			raise e

	def update_if_necessary(self, sleep_method):
		log.debug("update if necessary")

		td = datetime.now() - self.last_update_timestamp
		self.dev.updateStateOnServer(key="secondsSinceLastUpdate", value=_timedelta_to_seconds(td), decimalPlaces=0,
									 uiValue=_minutes_to_dms(_timedelta_to_minutes(td)))

		if datetime.now() > self.next_update_timestamp:

			try:
				self.request_and_update_status(sleep_method)
			except HTTPError as e:
				log.error("HTTP error connecting to Nissan's servers; will try again later (%s)" % e)
				log.debug(e.read())
				self.update_again_in_x_seconds(60 * self.error_update_frequency_minutes)
			except CarwingsError as e:
				log.error("Carwings error connecting to Nissan's servers; will try again later (%s)" % e)
				self.update_again_in_x_seconds(60 * self.error_update_frequency_minutes)

		else:
			log.debug("not time to update yet")

	def request_and_update_status(self, sleep_method):
		log.debug("request and update status")
		result_key = self.request_status()
		total_wait = 0
		for i in [30, 120, 120, 150, 180]:
			log.info("sleeping for %ss to give nissan's server time to retrieve updated status from vehicle" % i)
			sleep_method(i)
			total_wait += i
			if self.update_status(result_key):
				break
		else:
			log.warn("nissan did not return an updated status after %ss of waiting; giving up this time" % total_wait)
			self.update_again_in_x_seconds(60 * self.error_update_frequency_minutes)
			return False

		return True

	def update_again_in_x_seconds(self, sec):
		self.next_update_timestamp = datetime.now() + timedelta(seconds=sec)

	def request_status(self):
		log.info("requesting status for %s" % self.vin)
		if not self.leaf:
			log.info("not yet logged in; doing that first")
			self.login()
		try:
			result_key = self.leaf.request_update()
		except pycarwings2.pycarwings2.CarwingsError as e:
			log.warn("error requesting status")
			raise e
#			self.login()
#			self.vehicleservice.request_status(self.vin)
		return result_key

	# Returns True if retrieved status had a different time stamp than last
	# time we updated; False otherwise.
	def update_status(self, result_key):
#		if not self.connection.logged_in:
#			self.login()
		log.info("updating status for %s" % self.vin)
		try:
			status = self.leaf.get_status_from_update(result_key)
		except pycarwings2.pycarwings2.CarwingsError:
			log.warn("error getting latest status; logging in again and retrying")
			self.login()
			status = self.leaf.get_status_from_update(result_key)

		log.debug("status: %s" % yaml.dump(status))

		if not status:
			log.info("no status check result yet")
			return False

		self.dev.updateStateOnServer(key="batteryCapacity", value=status.battery_capacity)
		self.dev.updateStateOnServer(key="batteryRemainingCharge", value=status.battery_degradation)

		self.dev.updateStateOnServer(key="connected", value=status.is_connected)
		self.dev.updateStateOnServer(key="connectedQuickCharger", value=status.is_connected_to_quick_charger)

		IndigoLeaf.distance_format.report(self.dev, "cruisingRangeACOff", status.cruising_range_ac_off_km)
		IndigoLeaf.distance_format.report(self.dev, "cruisingRangeACOn", status.cruising_range_ac_on_km)

		self.dev.updateStateOnServer(key="chargingStatus", value=status.charging_status)
		self.dev.updateStateOnServer(key="charging", value=status.is_charging)
		self.dev.updateStateOnServer(key="quickCharging", value=status.is_quick_charging)

		self.dev.updateStateOnServer(key="pluginState", value=status.plugin_state)

		status2 = self.leaf.get_latest_battery_status()

		if status2.time_to_full_trickle:
			time_to_full = _timedelta_to_minutes(status2.time_to_full_trickle)
			self.dev.updateStateOnServer(key="timeToFullTrickle", value=time_to_full, decimalPlaces=0,
										uiValue=_minutes_to_dms(time_to_full))
		else:
			# no data; use -1 value to indicate
			self.dev.updateStateOnServer(key="timeToFullTrickle", value=-1, decimalPlaces=0,
										uiValue="-")

		if status2.time_to_full_l2:
			time_to_full_l2 = _timedelta_to_minutes(status2.time_to_full_l2)
			self.dev.updateStateOnServer(key="timeToFullL2", value=time_to_full_l2, decimalPlaces=0,
										uiValue=_minutes_to_dms(time_to_full_l2))
		else:
			# no data; use -1 value to indicate
			self.dev.updateStateOnServer(key="timeToFullL2", value=-1, decimalPlaces=0,
										uiValue="-")

		if status2.time_to_full_l2_6kw:
			time_to_full_l2_6kw = _timedelta_to_minutes(status2.time_to_full_l2_6kw)
			self.dev.updateStateOnServer(key="timeToFullL2_6kw", value=time_to_full_l2_6kw, decimalPlaces=0,
										uiValue=_minutes_to_dms(time_to_full_l2_6kw))
		else:
			# no data; use -1 value to indicate
			self.dev.updateStateOnServer(key="timeToFullL2_6kw", value=-1, decimalPlaces=0,
										uiValue="-")

		self.dev.updateStateOnServer(key="batteryLevel", value=status.battery_percent, decimalPlaces=0,
									uiValue=u"%s%%" % "{0:.0f}".format(status.battery_percent))

		self.charging = status.is_charging


		# 'battery' state images are not yet available, so use sort-of-close icons
		# instead, for now.
		if status.is_charging:
#			log.debug("using 'charger on' icon")
#			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryChargerOn)
			log.debug("using 'power on' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
		elif status.is_connected:
			# log.debug("using 'charger off' icon")
			# self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryCharger)
			log.debug("using 'power off' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)
		# elif status.battery_percent >= 87.5:
		# 	log.debug("using 'battery high' icon")
		# 	self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevelHigh)
		# elif status.battery_percent >= 62.5:
		# 	log.debug("using 'battery 75' icon")
		# 	self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevel75)
		elif status.battery_percent > 37.5:
			# log.debug("using 'battery 50' icon")
			# self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevel50)
			log.debug("using 'sensor on' (green) icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
		elif status.battery_percent > 15:
			# log.debug("using 'battery 25' icon")
			# self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevel25)
			log.debug("using 'sensor off' (gray) icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
		else:
			# log.debug("using 'battery low' icon")
			# self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevelLow)
			log.debug("using 'sensor tripped' (red) icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.SensorTripped)

		status3 = self.leaf.get_latest_hvac_status()
		if status3 is None:
			log.warn("could not retrieve HVAC state from server")
		else:
			self.dev.updateStateOnServer(key="climateControl", value=status3.is_hvac_running)

		self.last_update_timestamp = datetime.now()
		self.dev.updateStateOnServer(key="lastUpdateTimestamp", value=self.last_update_timestamp.ctime())
		self.dev.updateStateOnServer(key="secondsSinceLastUpdate", value=0)

		if status.is_charging:
			self.update_again_in_x_seconds(60 * self.charging_update_frequency_minutes)
		else:
			self.update_again_in_x_seconds(60 * self.not_charging_update_frequency_minutes)

		log.info("finished updating status for %s; next update at %s" % (self.vin, self.next_update_timestamp.ctime()))

		return True
