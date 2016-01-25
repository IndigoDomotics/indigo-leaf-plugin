#! /usr/bin/env python
# -*- coding: utf-8 -*-

FORMAT_STRING = "{0:.1f}"

class DistanceScale:

	def report(self, dev, stateKey, reading):
		txt = self.format(reading)
		dev.updateStateOnServer(key=stateKey, value=self.convert(reading), decimalPlaces=1, uiValue=txt)
		return txt

	def format(self, reading):
		return u"%s%s" % (FORMAT_STRING.format(self.convert(reading)), self.suffix())

class Kilometers(DistanceScale):
	def convert(self, reading):
		return float(reading) / 1000
	def suffix(self):
		return u"km"

class Miles(DistanceScale):
	def convert(self, reading):
		return float(reading) * 0.000621371
	def suffix(self):
		return u"mi"

class Furlongs(DistanceScale):
	def convert(self, reading):
		return float(reading) * 0.000621371 * 8.0
	def suffix(self):
		return u"fur"
