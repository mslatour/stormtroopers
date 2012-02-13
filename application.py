import domination.run
import sys

class MyScenario(domination.run.Scenario):
  EPISODES = 10

def run(mode):
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
  if len(sys.argv) == 1:
    print "Usage: python application.py <mode>"
  else:
    run(sys.argv[1])
