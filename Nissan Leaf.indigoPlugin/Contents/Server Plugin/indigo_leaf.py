import yaml
import indigo
import logging

import pycarwings2

import distance_scale

CONNECTED_VALUE_MAP = {
	'CONNECTED': True,
	'NOT_CONNECTED'  : False
}

CHARGING_VALUE_MAP = {
	'NORMAL_CHARGING': True, # still valid?
	'220V': True,
	'NOT_CHARGING'  : False
}

DISTANCE_SCALE_MAP = {
	"k" : distance_scale.Kilometers(),
	"m" : distance_scale.Miles(),
	"f" : distance_scale.Furlongs()
}

log = logging.getLogger('indigo.nissanleaf.plugin')

class IndigoLeaf:

	# class variables
	session = None
	distance_format = distance_scale.Miles()

	vins = []

	@staticmethod
	def setup(username, password, region):
		log.debug("indigoleaf setup; username: %s" % username)
		IndigoLeaf.session = pycarwings2.pycarwings2.Session(username, password) # region TBD
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

	def __init__(self, dev, plugin):
		log.debug("IndigoLeaf object init")
		self.dev = dev
		self.leaf = None

		if "address" in dev.pluginProps:
			# version 0.0.3
			self.vin = dev.pluginProps["address"]
		elif "vin" in dev.pluginProps:
			# version 0.0.1
			self.vin = dev.pluginProps["vin"]
		else:
			log.error("couldn't find a property with the VIN: %s" % dev.pluginProps)


	def start_charging(self):
		pass
#		if not self.connection.logged_in:
#			self.login()
#		try:
#			self.vehicleservice.start_charge(self.vin)
#		except CarwingsError:
#			log.warn("error starting charging; logging in again and retrying")
#			self.login()
#			self.vehicleservice.start_charge(self.vin)

	def start_climate_control(self):
		pass
#		if not self.connection.logged_in:
#			self.login()
#		try:
#			self.vehicleservice.start_ac_now(self.vin)
#		except CarwingsError:
#			log.warn("error starting climate control; logging in again and retrying")
#			self.login()
#			self.vehicleservice.start_ac_now(self.vin)

	def request_and_update_status(self, sleep_method):
		log.debug("request and update status")
		result_key= self.request_status()

		log.info("sleeping for 30s to give nissan's server time to retrieve updated status from vehicle")
		sleep_method(30)

		for i in range(2):
			if self.update_status(result_key):
				break
			log.info("sleeping for an additional 120s to give nissan's server more time to retrieve updated status from vehicle")
			sleep_method(120)
		else:
			log.warn("nissan did not return an updated status after five minutes of waiting; giving up this time")
			return False

		return True


	def request_status(self):
		log.info("requesting status for %s" % self.vin)
		if not self.leaf:
			log.info("not yet logged in; doing that first")
			self.login()
		try:
			result_key = self.leaf.request_update()
		except pycarwings2.pycarwings2.CarwingsError as e:
			log.warn("error requesting status; logging in again and retrying")
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

		self.dev.updateStateOnServer(key="batteryCapacity", value=status["batteryCapacity"])
		self.dev.updateStateOnServer(key="batteryRemainingCharge", value=status["batteryDegradation"])

		try:
			is_connected = CONNECTED_VALUE_MAP[status["pluginState"]]
		except KeyError:
			log.error(u"Unknown connected state: '%s'" % status["pluginState"])
			is_connected = True # probably
		self.dev.updateStateOnServer(key="connected", value=is_connected)

		IndigoLeaf.distance_format.report(self.dev, "cruisingRangeACOff", status["cruisingRangeAcOff"])
		IndigoLeaf.distance_format.report(self.dev, "cruisingRangeACOn", status["cruisingRangeAcOn"])

		self.dev.updateStateOnServer(key="chargingStatus", value=status["chargeMode"])
		try:
			is_charging = CHARGING_VALUE_MAP[status["chargeMode"]]
		except KeyError:
			log.error(u"Unknown charging state: '%s'" % status["chargeMode"])
			is_charging = True # probably
		self.dev.updateStateOnServer(key="charging", value=is_charging)

		time_to_full = self._time_remaining(status["timeRequiredToFull"])
		self.dev.updateStateOnServer(key="timeToFullTrickle", value=time_to_full, decimalPlaces=0,
									uiValue=str(time_to_full)+"m")

		time_to_full_l2 = self._time_remaining(status["timeRequiredToFull200"])
		self.dev.updateStateOnServer(key="timeToFullL2", value=time_to_full_l2, decimalPlaces=0,
									uiValue=str(time_to_full_l2)+"m")


		pct = 100 * float(status["batteryDegradation"]) / float(status["batteryCapacity"])
		self.dev.updateStateOnServer(key="batteryLevel", value=pct, decimalPlaces=0,
									uiValue=u"%s%%" % "{0:.0f}".format(pct))

		if is_charging:
			log.debug("using 'charger on' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryChargerOn)
		elif is_connected:
			log.debug("using 'charger off' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryCharger)
		elif pct >= 87.5:
			log.debug("using 'battery high' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevelHigh)
		elif pct >= 62.5:
			log.debug("using 'battery 75' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevel75)
		elif pct > 37.5:
			log.debug("using 'battery 50' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevel50)
		elif pct > 15:
			log.debug("using 'battery 25' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevel25)
		else:
			log.debug("using 'battery low' icon")
			self.dev.updateStateImageOnServer(indigo.kStateImageSel.BatteryLevelLow)

		log.info("finished updating status for %s" % self.vin)

		return True

	def _time_remaining(self, t):
		minutes = float(0)
		if t:
			if t["hours"]:
				minutes = float(60*t["hours"])
			if t["minutes"]:
				minutes += t["minutes"]
		return minutes
