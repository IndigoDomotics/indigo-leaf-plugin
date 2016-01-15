# indigo-leaf-plugin
Plugin for [Indigo home automation software][indigo] to support Nissan Leaf API.

Embeds several Python libraries:
* [pycarwings][pycarwings]: Python library for invoking the API from Nissan
* [iso8601][iso8601]: date library required by pycarwings
* [PyYAML][pyyaml]: YAML support; only used for logging at the moment, so it may be removed in a later version

### Known Limitations
* Remaining travel distance reported only in kilometers
* Only supports a single Nissan Leaf per login account
* "start charging" and "start climate control" actions have been implemented, but not yet tested
* Doesn't read current climate control state (because I'm not sure how to determine it)
* Icons don't display next to the Leaf device. I'm setting them based on the current status of the battery and charger, but they don't show up. I presume this is an Indigo issue, given the note in the Indigo API documentation: *note Indigo Touch and Indigo client UI do not currently have icons for every image selector listed below.*


[pycarwings]: https://github.com/haykinson/pycarwings
[iso8601]: https://pypi.python.org/pypi/iso8601
[pyyaml]: http://pyyaml.org
[indigo]: http://www.indigodomo.com
