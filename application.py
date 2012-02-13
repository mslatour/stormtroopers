import domination.run
import sys

DEFAULT_RUN_SETTINGS = {
  'mode': "default",
  'verbose': "True",
  'render': "True"
}

class MyScenario(domination.run.Scenario):
  EPISODES = 10

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
  mode = settings["mode"]
  if mode == "sander":
    MyScenario.test('trooper_sander.py', 'domination/agent.py')
  elif mode == "frank":
    MyScenario.test('trooper_frank.py', 'domination/agent.py')
  elif mode == "daniel":
    MyScenario.test('trooper_daniel.py', 'domination/agent.py')
  elif mode == "sicco":
    MyScenario.test('trooper_sicco.py', 'domination/agent.py')
  else:
    MyScenario.test('trooper.py', 'domination/agent.py')

if __name__ == "__main__":
  if len(sys.argv) == 2 and sys.argv[1] == "--help":
    print "Usage: python application.py [<settings>]"
    print " Settings:"
    print " ---------------------------------------------------------------"
    print " | Setting:  | Default:  | Values:                             |"
    print " ---------------------------------------------------------------"
    print " | --mode    | default   | {default|sander|frank|daniel|sicco} |"
    print " | --verbose | True      | {True|False}                        |"
    print " | --render  | True      | {True|False}                        |"
    print " ---------------------------------------------------------------"
  else:
    run(applySettings(sys.argv))
