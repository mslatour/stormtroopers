import domination.run
import sys
import pickle

DEFAULT_RUN_SETTINGS = {
  'agent': "default",
  'mode': "test",
  'verbose': "True",
  'render': "True",
  'output': None,
  'replay': None
}

DEFAULT_OPPONENT = "domination/agent.py"

AGENT_MAPPINGS = {
  "default" : "trooper.py",
  "daniel" : "trooper_daniel.py",
  "frank"  : "trooper_frank.py",
  "sicco"  : "sicco.py",
  "sander" : "trooper_sander.py",
  "offence" : "offence_trooper.py",
  "defence" : "defence_trooper.py",
  "reactive" : "reactive_trooper.py"
}

class MyScenario(domination.run.Scenario):
  REPEATS = 50

def applySettings(args):
  settings = DEFAULT_RUN_SETTINGS
  name = None
  value = None
  for arg in args[1:]:
    if arg[0:2] == "--":
      name = arg[2:]
    elif name is not None:
      settings[name] = arg
      name == None
  return settings

def run(settings):
  print settings
  if settings["replay"] is not None:
    replay = pickle.load(open(settings["replay"], 'rb'))
    replay.play()
  else:
    try:
      {
        "test" : lambda x: MyScenario.test(
          AGENT_MAPPINGS[x["agent"]], DEFAULT_OPPONENT
        ),
        "one_on_one" : lambda x: MyScenario.one_on_one(
          AGENT_MAPPINGS[x["agent"]], 
          DEFAULT_OPPONENT,
          x["output"]
        )
      }[settings["mode"]](settings)
    except KeyError:
      print "Unsupported option, check --help for valid options"

if __name__ == "__main__":
  if len(sys.argv) == 2 and sys.argv[1] == "--help":
    print "Usage: python application.py [<settings>]"
    print " Settings:"
    print " .-------------------------------------------------------------."
    print " | Setting:  | Default:  | Values:                             |"
    print " |-------------------------------------------------------------|"
    print " | --replay  | None      | Path to pickle file                 |"
    print " | --agent   | default   | {default|sander|frank|daniel|sicco  |"
    print " |                          offence|defence|reactive}          |"
    print " | --mode    | test      | {test|one_on_one|replay}            |"
    print " | --output  | None      | A valid directory                   |"
    print " | --verbose | True      | {True|False}                        |"
    print " | --render  | True      | {True|False}                        |"
    print " '-------------------------------------------------------------'"
  else:
    run(applySettings(sys.argv))
