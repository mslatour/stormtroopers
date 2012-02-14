import time

# Parameters
CROWDED_HOTSPOT = 3
SUFFICIENT_AMMO = 3
PEACE_THRESHOLD = 5

# World knowledge
NUM_AMMO_SPOTS = 6

# Behavior settings:
SETTINGS_DEAD_CANT_THINK = True

# Feature settings
SETTINGS_PEACE_ADDS_UP = True

# Debug settings
SETTINGS_DEBUG_ON = True
SETTINGS_DEBUG_SHOW_VISIBLE_OBJECTS = True
SETTINGS_DEBUG_SHOW_VISIBLE_FOES = True
SETTINGS_DEBUG_SHOW_ID = True
SETTINGS_DEBUG_SHOW_MOTIVATION = True
SETTINGS_DEBUG_SHOW_AMMO = True
SETTINGS_DEBUG_SHOW_PEACE_ZONES = True
SETTINGS_DEBUG_SHOW_KNOWN_AMMO_SPOTS = True

#######################
# Various motivations #
# ------------------- ##############
# Used to keep track of the        #
# original reason to go somewhere  #
# to check if it is still accurate #
###################################

# Motivation: Capture a enemy control point
MOTIVATION_CAPTURE_CP = 'C'
# Motivation: Guard a friendly control point
MOTIVATION_GUARD_CP = 'G'
# Motivation: Pickup ammo pack
MOTIVATION_AMMO = 'A'
# Motivation: User clicked
MOTIVATION_USER_CLICK = 'U'
# Motivation: Shoot an enemy
MOTIVATION_SHOOT_TARGET = 'S'

########
# Ideas:
# - Guard CP's without any friends
# - Abandon peacefull CPs to give backup to
#   the more restless CPs
# - Improve the path planning

class Agent(object):
  
  NAME = "TrooperDaniel"
  attack_strat1 = False

  # Location of the home base
  home_base = None
  enemy_base = None

  # Mapping between CPs
  # and number of agents who
  # are there
  hotspot = {}

  # Mapping between CPs
  # and number of agents who 
  # are going there
  trendingSpot = {}

  # Mapping between friendly CPs
  # and the amount of steps it has
  # been in friendly hands
  inFriendlyHands = {}

  # List of CPs in friendly hands
  friendlyCPs = []

  # List of CPs in enemy hands
  enemyCPs = []

  # Amount of turns (time steps)
  time = 0

  # Ammo locations
  ammoSpots = []
    
  def __init__(self, id, team, settings=None, field_rects=None, field_grid=None, nav_mesh=None):
    """ Each agent is initialized at the beginning of each game.
        The first agent (id==0) can use this to set up global variables.
        Note that the properties pertaining to the game field might not be
        given for each game.
    """
    self.id = id
    self.team = team
    self.mesh = nav_mesh
    self.grid = field_grid
    self.settings = settings
    self.motivation = None
    self.goal = None
    if SETTINGS_DEBUG_ON:
      self.log = open(("log%d.txt" % id),"w")
        
    # Recommended way to share variables between agents.
    if id == 0:
      self.all_agents = self.__class__.all_agents = []
    self.all_agents.append(self)
    
    if(id == 1 | id == 2):
      self.attack_strat1 = True
    
  
  def observe(self, observation):
    """ Each agent is passed an observation using this function,
        before being asked for an action. You can store either
        the observation object or its properties to use them
        to determine your action. Note that the observation object
        is modified in place.
    """
    self.observation = observation
    self.selected = observation.selected
      
  def action(self):
    """ This function is called every step and should
        return a tuple in the form: (turn, speed, shoot)
    """
    obs = self.observation
    
    # Set statistics for this turn
    # if current agent is the first
    if self.id == 0:
      self.__class__.time += 1
      self.setTurnStats()
    
    if SETTINGS_DEAD_CANT_THINK and obs.respawn_in > -1:
      if self.__class__.home_base is None:
        self.debugMsg("Found home base at %s" % (obs.loc,))
        self.__class__.home_base = obs.loc
      self.debugMsg("Sleeping")
      return (0,0,0)

    self.debugMsg("Foes: %s" % (obs.foes,))
    ###### CHECK IF AGENT (STILL) HAS A GOAL ###### 
    # Check if agent reached goal.
    if self.goal is not None and point_dist(self.goal, obs.loc) < self.settings.tilesize:
      self.goal = None

    # If agent already has a goal
    # check if the motivation is still accurate
    if self.goal is not None:
      self.validateMotivation()

    if self.goal is not None:
      self.log.write("*> Go to: (%d,%d)" % (self.goal[0], self.goal[1]))
      
    ###### LISTEN TO USER INPUT ######   
    
    # Drive to where the user clicked
    if self.selected and self.observation.clicked:
      self.motivation = MOTIVATION_USER_CLICK
      self.goal = self.observation.clicked
     
    ###### UPDATE AMMO OBSERVATION######
    ammopacks = filter(lambda x: x[2] == "Ammo", obs.objects)
    if ammopacks:
      self.updateAllAmmoSpots(ammopacks)
     
    ###### START ACTING ###### 
    
    #Make sure that agent always has some ammo
    if self.goal is not None:
      # Walk to ammo
      if obs.ammo < SUFFICIENT_AMMO:
        self.goal = self.getClosestLocation(ammopacks)
        self.motivation = MOTIVATION_AMMO
        self.debugMsg("*> Recharge (%d,%d)" % (self.goal[0],self.goal[1]))

    #Attack strategy 1
    if self.goal is None & self.attack_strat1:
      self.executeStrategy('attack1')
   
    # Shoot enemies
    shoot = False
    if (obs.ammo > 0 and 
        obs.foes and 
        point_dist(obs.foes[0][0:2], obs.loc) < self.settings.max_range
        and not line_intersects_grid(obs.loc, obs.foes[0][0:2], self.grid, self.settings.tilesize)):
      self.goal = obs.foes[0][0:2]
      self.motivation = MOTIVATION_SHOOT_TARGET
      self.debugMsg("*> Shoot (%d,%d)" % (self.goal[0],self.goal[1]))
      shoot = True

    #Backup strategies:#

    # Walk to an enemy CP
    if self.goal is None:
      self.goal = self.getClosestLocation(self.getQuietEnemyCPs())
      self.debugMsg("Crowded location: %d" % self.getCrowdedValue(self.goal))
      if self.goal is not None:
        self.motivation = MOTIVATION_CAPTURE_CP
        self.debugMsg("*> Capture (%d,%d)" % (self.goal[0],self.goal[1]))

    # If you can't think of anything to do
    # at least walk to a friendly control point
    if self.goal is None:
      self.goal = self.getClosestLocation(self.getQuietRestlessFriendlyCPs())
      if self.goal is not None:
        self.motivation = MOTIVATION_GUARD_CP
        self.debugMsg("*> Guard (%d,%d)" % (self.goal[0],self.goal[1]))
    
    ######## COMPUTE ACTUAL ACTION OUTPUT ########
    
    # Compute path, angle and drive
    path = find_path(obs.loc, self.goal, self.mesh, self.grid, self.settings.tilesize)
    if path:
      dx = path[0][0]-obs.loc[0]
      dy = path[0][1]-obs.loc[1]
      turn = angle_fix(math.atan2(dy, dx)-obs.angle)
      if turn > self.settings.max_turn or turn < -self.settings.max_turn:
          shoot = False
      speed = (dx**2 + dy**2)**0.5
    else:
      turn = 0
      speed = 0

    self.updateTrendingSpot()

    return (turn,speed,shoot)

  def executeStrategy(self, strategy):
    if strategy == 'attack1':
      print 'executing attack strategy 1'
      self.debugMsg('executing attack strategy 1')
      #if not within range of enemy spawn point:
        #go to enemy spawn point
      #if near enemy spawn point and no enemy
        #search for ammo within range

  def debugMsg(self, msg):
    if SETTINGS_DEBUG_ON:
      self.log.write("[%d-%f]: %s\n" % (self.__class__.time, time.time(), msg))
      self.log.flush()

  def setTurnStats(self):
    obs = self.observation
    # Reset trendingSpot
    self.__class__.trendingSpot = {}
    
    # Update friendly CPs
    self.__class__.friendlyCPs = map(lambda x: x[0:2], 
      filter(lambda x: x[2] == self.team, obs.cps))
    
    # Update enemy CPs
    self.__class__.enemyCPs = map(lambda x:x[0:2], 
      filter(lambda x: x[2] != self.team, obs.cps))

    # Update inFriendlyHands stat
    if SETTINGS_PEACE_ADDS_UP:
      inFriendlyHands = self.__class__.inFriendlyHands
    else:
      inFriendlyHands = {}
    for cp in self.__class__.friendlyCPs:
      if cp in self.__class__.inFriendlyHands:
        inFriendlyHands[cp] = self.__class__.inFriendlyHands[cp] + 1
      else:
        inFriendlyHands[cp] = 1
    self.__class__.inFriendlyHands = inFriendlyHands

  def updateTrendingSpot(self):
    if self.goal is not None:
      if self.goal in self.__class__.trendingSpot:
        self.__class__.trendingSpot[self.goal].append(self.id)
      else:
        self.__class__.trendingSpot[self.goal] = [self.id]

    self.debugMsg("[HS: %s]" % (self.__class__.trendingSpot,))
    self.debugMsg(
      (
        "[MAXHS: %d]" % max(
          map(
            lambda x: len(self.__class__.trendingSpot[x]),
            self.__class__.trendingSpot
          )
        )
      )
    )

  def updateAllAmmoSpots(self, spots):
    if len(self.__class__.ammoSpots) < NUM_AMMO_SPOTS:
      for spot in spots:
        self.updateAmmoSpots(spot)

  def updateAmmoSpots(self, spot):
    if spot[0:2] not in self.__class__.ammoSpots:
      self.__class__.ammoSpots.append(spot[0:2])

  def validateMotivation(self):
    obs = self.observation
    self.debugMsg("[MOT: %s]" % (self.motivation,))
    if self.motivation == MOTIVATION_CAPTURE_CP:
      # If the CP to be captures is already friendly, stop.
      if (
          self.goal in self.__class__.friendlyCPs or
          self.getCrowdedValue(self.goal) >= CROWDED_HOTSPOT
      ):
        self.goal = None
        self.motivation = None
    elif self.motivation == MOTIVATION_GUARD_CP:
      if len(self.__class__.enemyCPs) > 0:
        self.goal = None
        self.motivation = None
    elif self.motivation == MOTIVATION_AMMO:
      if ((self.goal[0], self.goal[1], 'Ammo') not in obs.objects):
        self.goal = None
        self.motivation = None
    elif self.motivation == MOTIVATION_SHOOT_TARGET:
      if self.goal not in map(lambda x: x[0:2], obs.foes):
        self.goal = None
        self.motivation = None
    

  ############################
  # Methods used to retrieve #
  #  information out of the  #
  #   current observations   #
  ############################

  def getEuclidDist(self, c1, c2):
    return abs(c1[0]-c2[0])+abs(c1[1]-c2[1])
  
  def getHotspotValue(self, coord):
    if coord in self.__class__.hotspot:
      return len(self.__class__.hotspot[coord])
    else:
      return 0

  def getTrendingSpotValue(self, coord):
    if coord in self.__class__.trendingSpot:
      return len(self.__class__.trendingSpot[coord])
    else:
      return 0

  def getCrowdedValue(self, coord):
    return self.getTrendingSpotValue(coord) + self.getHotspotValue(coord)

  def getPeaceValue(self, coord):
    if coord in self.__class__.inFriendlyHands:
      return self.__class__.inFriendlyHands[coord]/float(self.__class__.time)
    else:
      return 0

  # Safety score based on:
  # - distance to home base
  # - peace value
  # - hotspot value
  # - distance to a known ammo spot
  def getSafetyScore(self, coord):
    return (
      self.getPeaceValue(coord)
#      - self.getEuclidDist(coord, self.__class__.home_base)
#      - min(map(lambda x: getEuclidDist(coord, x), self.__class__.ammoSpots))
#      - self.getCrowdedValue(coord)
    )

  def getEnemyCPs(self):
    return filter(lambda x: x[2] != self.team, self.observation.cps)

  def getQuietEnemyCPs(self):
    return filter((lambda x: x[2] != self.team and
      self.getCrowdedValue(x[0:2]) < CROWDED_HOTSPOT), self.observation.cps)

  def getFriendlyCPs(self):
    return filter(lambda x: x[2] == self.team, self.observation.cps)

  def getQuietFriendlyCPs(self):
    return filter(( lambda x: x[2] == self.team and 
      self.getCrowdedValue(x[0:2]) < CROWDED_HOTSPOT), self.observation.cps)
  
  def getQuietRestlessFriendlyCPs(self):
    return filter(( lambda x: x[2] == self.team and 
      self.getPeaceValue(x[0:2]) < PEACE_THRESHOLD and
      self.getCrowdedValue(x[0:2]) < CROWDED_HOTSPOT), self.observation.cps)

  def getClosestLocation(self, locations):
    """ Returns the closest enemy control point
        in terms of euclid distance from the 
        current agent coordinates that is not
        already visited by more than one other
        agent.
    """
    obs = self.observation

    if len(locations) > 0:
      min_i = 0
      min_dist = self.getEuclidDist(obs.loc, locations[0][0:2])
      for i in range(1, len(locations)):
        dist = self.getEuclidDist(obs.loc, locations[1][0:2])
        if dist < min_dist:
          min_i = i
          min_dist = dist
      return locations[min_i][0:2]
    else:
      return None

  def debug(self, surface):
    """ Allows the agents to draw on the game UI,
        Refer to the pygame reference to see how you can
        draw on a pygame.surface. The given surface is
        not cleared automatically. Additionally, this
        function will only be called when the renderer is
        active, and it will only be called for the active team.
    """
    import pygame
    if self.id == 0:
      # First agent clears the screen
      surface.fill((0,0,0,0))
      if SETTINGS_DEBUG_ON:
        if SETTINGS_DEBUG_SHOW_PEACE_ZONES:
          self.drawPeaceZones(pygame, surface)
        if SETTINGS_DEBUG_SHOW_KNOWN_AMMO_SPOTS:
          self.drawKnownAmmoSpots(pygame, surface)
  
    # Selected agents draw their info
    if self.selected:
      if self.goal is not None:
        pygame.draw.line(surface,(0,0,0),self.observation.loc, self.goal)
      if SETTINGS_DEBUG_ON:
        if SETTINGS_DEBUG_SHOW_VISIBLE_OBJECTS:
          self.drawVisibleObjects(pygame, surface)
        if SETTINGS_DEBUG_SHOW_VISIBLE_FOES:
          self.drawVisibleFoes(pygame, surface)
        self.drawDebugTextSurface(pygame, surface)
  
  def drawVisibleFoes(self, pygame, surface):
    for o in self.observation.foes:
      pygame.draw.line(surface, (127,127,127), self.observation.loc, o[0:2])
  
  def drawVisibleObjects(self, pygame, surface):
    for o in self.observation.objects:
      pygame.draw.line(surface, (255,255,255), self.observation.loc, o[0:2])

  def drawPeaceZones(self, pygame, surface):
    font = pygame.font.Font(pygame.font.get_default_font(), 10)
    for cp in self.observation.cps:
      txt = font.render(
        "%.2f" % (self.getPeaceValue(cp[0:2]),), 
        True,
        (0,0,255)
      )
      surface.blit(txt, cp[0:2])

  def drawKnownAmmoSpots(self, pygame, surface):
    font = pygame.font.Font(pygame.font.get_default_font(), 10)
    for spot in self.__class__.ammoSpots:
      txt = font.render("*", False, (255,255,255))
      surface.blit(txt, spot)
    
  def drawDebugTextSurface(self, pygame, surface):
    x = self.observation.loc[0]
    y = self.observation.loc[1]
    font = pygame.font.Font(pygame.font.get_default_font(), 10)
    if SETTINGS_DEBUG_SHOW_ID:
      # Draw id
      txt_id = font.render("%d" % (self.id,), True, (0,0,0))
      surface.blit(txt_id, (x+10,y-10))
    if SETTINGS_DEBUG_SHOW_MOTIVATION:
      # Draw motivation
      if self.motivation is not None:
        txt_mot = font.render("%s" % (self.motivation,), True, (0,0,255))
        surface.blit(txt_mot, (x+10,y+5))
    if SETTINGS_DEBUG_SHOW_AMMO:
      # Draw ammo
      txt_ammo = font.render("%d" % (self.observation.ammo,), True, (255,0,0))
      surface.blit(txt_ammo, (x-10,y-10))


  def finalize(self, interrupted=False):
    """ This function is called after the game ends, 
        either due to time/score limits, or due to an
        interrupt (CTRL+C) by the user. Use it to
        store any learned variables and write logs/reports.
    """
    pass
 
AS_STRING = """
class Agent(object):
 NAME="default_agent"
 def __init__(self,id,team,settings=None,field_rects=None,field_grid=None,nav_mesh=None):
  self.id=id
  self.team=team
  self.mesh=nav_mesh
  self.grid=field_grid
  self.settings=settings
  self.goal=None
  if id==0:
   self.all_agents=self.__class__.all_agents=[]
  self.all_agents.append(self)
 def observe(self,observation):
  self.observation=observation
  self.selected=observation.selected
 def action(self):
  obs=self.observation
  if self.goal is not None and point_dist(self.goal,obs.loc)<self.settings.tilesize:
   self.goal=None
  ammopacks=filter(lambda x:x[2]=="Ammo",obs.objects)
  if ammopacks:
   self.goal=ammopacks[0][0:2]
  if self.selected and self.observation.clicked:
   self.goal=self.observation.clicked
  if self.goal is None:
   self.goal=obs.cps[random.randint(0,len(obs.cps)-1)][0:2]
  shoot=False
  if(obs.ammo>0 and obs.foes and point_dist(obs.foes[0][0:2],obs.loc)<self.settings.max_range and not line_intersects_grid(obs.loc,obs.foes[0][0:2],self.grid,self.settings.tilesize)):
   self.goal=obs.foes[0][0:2]
   shoot=True
  path=find_path(obs.loc,self.goal,self.mesh,self.grid,self.settings.tilesize)
  if path:
   dx=path[0][0]-obs.loc[0]
   dy=path[0][1]-obs.loc[1]
   turn=angle_fix(math.atan2(dy,dx)-obs.angle)
   if turn>self.settings.max_turn or turn<-self.settings.max_turn:
    shoot=False
   speed=(dx**2+dy**2)**0.5
  else:
   turn=0
   speed=0
  return(turn,speed,shoot)
 def debug(self,surface):
  import pygame
  if self.id==0:
   surface.fill((0,0,0,0))
  if self.selected:
   if self.goal is not None:
    pygame.draw.line(surface,(0,0,0),self.observation.loc,self.goal)
 def finalize(self,interrupted=False):
  pass
"""
