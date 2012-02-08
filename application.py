import domination.run

class MyScenario(domination.run.Scenario):
  EPISODES = 10

MyScenario.test('trooper.py', 'domination/agent.py')
