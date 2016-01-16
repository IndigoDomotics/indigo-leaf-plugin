# indigo-leaf-plugin
Plugin for [Indigo home automation software][indigo] to support Nissan Leaf API.

Embeds several Python libraries:
* [pycarwings][pycarwings]: Python library for invoking the API from Nissan
* [iso8601][iso8601]: date library required by pycarwings
* [PyYAML][pyyaml]: YAML support; only used for logging at the moment, so it may be removed in a later version

### Known Limitations
* Only supports a single Nissan Leaf per login account
* "start charging" and "start climate control" actions have been implemented, but not yet tested
* Doesn't read current climate control state (because I'm not sure how to determine it)
* Icons don't display next to the Leaf device. I'm setting them based on the current status of the battery and charger, but they don't show up. I presume this is an Indigo issue, given the note in the Indigo API documentation: *note Indigo Touch and Indigo client UI do not currently have icons for every image selector listed below.*
* The Leaf API endpoint can be unreliable; I've seen cases where the results reported were twelve hours old, despite the car being in an area with good cellular coverage.
* The plugin only updates once every fifteen minutes; this is to avoid causing heavy usage on the Nissan API endpoint (see previous point about unreliability) and to "stay beneath the radar" as the API access is through unofficial means.


[pycarwings]: https://github.com/haykinson/pycarwings
[iso8601]: https://pypi.python.org/pypi/iso8601
[pyyaml]: http://pyyaml.org
[indigo]: http://www.indigodomo.com
