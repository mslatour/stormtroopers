import time

##############################
##  *** Global Settings *** ##
####### *************** ######
##############################

##############
# Parameters #
##############
# Number of agents that make a spot crowded.
CROWDED_HOTSPOT = 3
# Range in pixels that still counts as the same hotspot.
HOTSPOT_RANGE = 20
# The number of turns before a control point is considered peaceful.
DOMINATION_THRESHOLD = 5
# Number of ammo that counts as enough.
SUFFICIENT_AMMO = 3

###################
# World knowledge #
###################
NUM_AMMO_SPOTS = 6
DEFAULT_FIELD_TILESIZE = 16 # in case not provided in settings
DEFAULT_FIELD_WIDTH = 41    # in case not provided in settings
DEFAULT_FIELD_HEIGHT = 26   # in case not provided in settings

#####################
# Behavior settings #
#####################
# Agents who died don't think about their destinations
SETTINGS_DEAD_CANT_THINK = True

####################
# Feature settings #
####################
# The domination value is cumulative.
SETTINGS_DOMINATION_ADDS_UP = True

##################
# Debug settings #
##################
SETTINGS_DEBUG_ON = False
SETTINGS_DEBUG_SHOW_VISIBLE_OBJECTS = True
SETTINGS_DEBUG_SHOW_VISIBLE_FOES = True
SETTINGS_DEBUG_SHOW_ID = True
SETTINGS_DEBUG_SHOW_MOTIVATION = True
SETTINGS_DEBUG_SHOW_AMMO = True
SETTINGS_DEBUG_SHOW_DOMINATION = True
SETTINGS_DEBUG_SHOW_KNOWN_AMMO_SPOTS = True
SETTINGS_DEBUG_SHOW_BASES = True

########################
# Motivation constants #
########################
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

class Agent(object):
  
  NAME = "Trooper"

  #########################
  # Extended observations #
  #########################

  # Location of the bases
  home_base = None
  enemy_base = None

  # Mapping between locations
  # and agents who are going there.
  trendingSpot = {}

  # Mapping between friendly CPs
  # and the amount of steps it has
  # been in friendly hands
  inFriendlyHands = {}

  # List of CPs in friendly hands
  friendlyCPs = []

  # List of CPs in enemy hands
  enemyCPs = []

  # Ammo locations
  ammoSpots = []

  ##################
  # Initialization #
  ##################
    
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

      tilesize = getattr(self.settings, 'tilesize', DEFAULT_FIELD_TILESIZE)
      if field_rects is None:
        self.__class__.field_width = DEFAULT_FIELD_WIDTH*tilesize
        self.__class__.field_height = DEFAULT_FIELD_HEIGHT*tilesize
      else:
        self.__class__.field_width = len(field_grid[0])*tilesize
        self.__class__.field_height = len(field_grid)*tilesize

      if SETTINGS_DEBUG_ON:
        self.debugMsg(
          "Field: %d x %d"
        % 
          (self.__class__.field_width, self.__class__.field_height)
        )
    self.all_agents.append(self)
  
  ############################
  # *  Observation methods * #
  ############################

  def observe(self, obs):
    """ Each agent is passed an observation using this function,
        before being asked for an action. You can store either
        the observation object or its properties to use them
        to determine your action. Note that the observation object
        is modified in place.
    """
    self.observation = obs
    self.selected = obs.selected
 
    #############################
    # Update of turn statistics #
    #############################
    if self.id == 0:
      # Store base locations
      if self.__class__.home_base is None:
        self.__class__.home_base = (obs.loc[0]+16, obs.loc[1]+8)
        self.__class__.enemy_base = \
          self.getSymmetricOpposite(self.__class__.home_base)
    
      # Reset trendingSpot
      self.__class__.trendingSpot = {}
      
      # Update friendly CPs
      self.__class__.friendlyCPs = map(lambda x: x[0:2], 
        filter(lambda x: x[2] == self.team, obs.cps))
      
      # Update enemy CPs
      self.__class__.enemyCPs = map(lambda x:x[0:2], 
        filter(lambda x: x[2] != self.team, obs.cps))

      # Update inFriendlyHands stat
      if SETTINGS_DOMINATION_ADDS_UP:
        inFriendlyHands = self.__class__.inFriendlyHands
      else:
        inFriendlyHands = {}
      for cp in self.__class__.friendlyCPs:
        if cp in self.__class__.inFriendlyHands:
          inFriendlyHands[cp] = self.__class__.inFriendlyHands[cp] + 1
        else:
          inFriendlyHands[cp] = 1
      self.__class__.inFriendlyHands = inFriendlyHands
  
  
  # Returns the opposite coordinate given the
  # symmetric property of the field
  def getSymmetricOpposite(self, coord):
    mid = round(self.__class__.field_width/2.0 + 0.5)
    if coord[0] > mid:
      return (mid-(coord[0]-mid), coord[1])
    else:
      return (mid+(mid-coord[0]), coord[1])

  # Registers goal in trending spot dictionary
  def updateTrendingSpot(self):
    if self.goal is not None:
      if self.goal in self.__class__.trendingSpot:
        self.__class__.trendingSpot[self.goal].append(self.id)
      else:
        self.__class__.trendingSpot[self.goal] = [self.id]

  # Registers (unknown) ammo spots
  def updateAllAmmoSpots(self, spots):
    if len(self.__class__.ammoSpots) < NUM_AMMO_SPOTS:
      for spot in spots:
        self._updateAmmoSpots(spot)
        self._updateAmmoSpots(self.getSymmetricOpposite(spot))

  # Auxilary method of updateAllAmmoSpots
  def _updateAmmoSpots(self, spot):
    if spot[0:2] not in self.__class__.ammoSpots:
      self.__class__.ammoSpots.append(spot[0:2])
  
  #########################
  # * Feature retrieval * #
  #########################

  # Returns the distance between
  # two coordinates using sqrt(dx^2+dy^2)
  def getEuclidDist(self, c1, c2):
    if c1 is None or c2 is None:
      return None
    return ((c1[0]-c2[0])**2+(c1[1]-c2[1])**2)**0.5
  
  # Returns the number of friends (not self)
  # that are near to the coordinate
  def getHotspotValue(self, coord):
    if coord is None:
      return None
    counter = 0
    for friend in self.observation.friends:
      if self.getEuclidDist(friend[0:2], coord) < HOTSPOT_RANGE:
        counter += 1
    return counter;

  # Returns the number of agents
  # that are going to the coordinate
  def getTrendingSpotValue(self, coord):
    if coord is None:
      return None
    if coord in self.__class__.trendingSpot:
      return len(self.__class__.trendingSpot[coord])
    else:
      return 0

  # Returns a metric representing the
  # amount of crowdness in the coordinate.
  # Uses both trendingSpot and hotspot values.
  def getCrowdedValue(self, coord):
    if coord is None:
      return None
    return self.getTrendingSpotValue(coord) + self.getHotspotValue(coord)

  # [Deprecated]
  # Use getDominationValue instead!
  def getPeaceValue(self, cp):
    self.getDominationValue(cp)

  # Returns the percentage of turns that the
  # control point has been in friendly hands
  def getDominationValue(self, cp):
    if cp is None:
      return None
    if cp in self.__class__.inFriendlyHands:
      return self.__class__.inFriendlyHands[cp]/float(self.observation.step)
    else:
      return 0

  # BETA!
  # Safety score based on:
  # - distance to home base
  # - domination value
  # - hotspot value
  # - distance to a known ammo spot
  def getSafetyScore(self, coord):
    return (
      self.getDominationValue(coord)
      + self.getCrowdedValue(coord)
      - self.getEuclidDist(coord, self.__class__.home_base)
      - min(map(lambda x: getEuclidDist(coord, x), self.__class__.ammoSpots))
    )

  # Returns the control points
  # that are in enemy hands
  def getEnemyCPs(self):
    return filter(lambda x: x[2] != self.team, self.observation.cps)

  # Returns the control points
  # that are in enemy hands
  # and have a low crowdedValue
  def getQuietEnemyCPs(self):
    return filter((lambda x: x[2] != self.team and
      self.getCrowdedValue(x[0:2]) < CROWDED_HOTSPOT), self.observation.cps)

  # Returns the control points
  # that are in friendly hands
  def getFriendlyCPs(self):
    return filter(lambda x: x[2] == self.team, self.observation.cps)

  # Returns the control points
  # that are in enemy hands
  # and have a low crowdedValue
  def getQuietFriendlyCPs(self):
    return filter(( lambda x: x[2] == self.team and 
      self.getCrowdedValue(x[0:2]) < CROWDED_HOTSPOT), self.observation.cps)
  
  # Returns the control points
  # that are in enemy hands
  # and have a low crowdedValue
  # and domination value
  def getQuietRestlessFriendlyCPs(self):
    return filter(( lambda x: x[2] == self.team and 
      self.getDominationValue(x[0:2]) < DOMINATION_THRESHOLD and
      self.getCrowdedValue(x[0:2]) < CROWDED_HOTSPOT), self.observation.cps)

  def getClosestLocation(self, locations):
    """ Returns the closest location from the set
        in terms of euclid distance to the current location
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

  #####################################
  # *  Action and strategy methods  * #
  #####################################
      
  def action(self):
    """ This function is called every step and should
        return a tuple in the form: (turn, speed, shoot)
    """
    obs = self.observation
    
    
    if SETTINGS_DEAD_CANT_THINK and obs.respawn_in > -1:
      self.debugMsg("Sleeping")
      return (0,0,0)

    self.debugMsg("Foes: %s" % (obs.foes,))

    # Check if agent reached goal.
    if self.goal is not None and point_dist(self.goal, obs.loc) < self.settings.tilesize:
      self.goal = None

    # If agent already has a goal
    # check if the motivation is still accurate
    if self.goal is not None:
      self.validateMotivation()

    if self.goal is not None:
      self.debugMsg("*> Go to: (%d,%d)" % (self.goal[0], self.goal[1]))
    
    # Drive to where the user clicked
    if self.selected and self.observation.clicked:
      self.motivation = MOTIVATION_USER_CLICK
      self.goal = self.observation.clicked
      
    ammopacks = filter(lambda x: x[2] == "Ammo", obs.objects)
    if ammopacks:
      self.updateAllAmmoSpots(ammopacks)

      if self.goal is not None:
        # Walk to ammo
        if obs.ammo < SUFFICIENT_AMMO:
          self.goal = self.getClosestLocation(ammopacks)
          self.motivation = MOTIVATION_AMMO
          self.debugMsg("*> Recharge (%d,%d)" % (self.goal[0],self.goal[1]))
   
    # Walk to an enemy CP
    if self.goal is None:
      self.goal = self.getClosestLocation(self.getQuietEnemyCPs())
      if self.goal is not None:
        self.debugMsg("Crowded location: %d" % self.getCrowdedValue(self.goal))
        self.motivation = MOTIVATION_CAPTURE_CP
        self.debugMsg("*> Capture (%d,%d)" % (self.goal[0],self.goal[1]))
    
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

    # If you can't think of anything to do
    # at least walk to a friendly control point
    if self.goal is None:
      self.goal = self.getClosestLocation(self.getQuietRestlessFriendlyCPs())
      if self.goal is not None:
        self.motivation = MOTIVATION_GUARD_CP
        self.debugMsg("*> Guard (%d,%d)" % (self.goal[0],self.goal[1]))
    
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

  # Checks if the current motivation to
  # go to the goal is still valid.
  # If not, it clears the goal and motivation
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
    
  #####################
  # * Debug methods * #
  #####################

  # Write a debug message to 
  # the agent's log file
  def debugMsg(self, msg):
    if SETTINGS_DEBUG_ON:
      if hasattr(self, 'observation'):
        self.log.write(
          "[%d-%f]: %s\n" % (self.observation.step, time.time(), msg))
      else:
        self.log.write(
          "[?-%f]: %s\n" % (time.time(), msg))
      self.log.flush()

  def debug(self, surface):
    """ Allows the agents to draw on the game UI,
        Refer to the pygame reference to see how you can
        draw on a pygame.surface. The given surface is
        not cleared automatically. Additionally, this
        function will only be called when the renderer is
        active, and it will only be called for the active team.
    """
    import pygame
    if self.id == 1:
      # First agent clears the screen
      surface.fill((0,0,0,0))
      if SETTINGS_DEBUG_ON:
        if SETTINGS_DEBUG_SHOW_DOMINATION:
          self._drawCPDomination(pygame, surface)
        if SETTINGS_DEBUG_SHOW_BASES:
          self._drawBases(pygame, surface)
        if SETTINGS_DEBUG_SHOW_KNOWN_AMMO_SPOTS:
          self._drawKnownAmmoSpots(pygame, surface)
  
    # Selected agents draw their info
    if self.selected:
      if self.goal is not None:
        pygame.draw.line(surface,(0,0,0),self.observation.loc, self.goal)
      if SETTINGS_DEBUG_ON:
        if SETTINGS_DEBUG_SHOW_VISIBLE_OBJECTS:
          self._drawVisibleObjects(pygame, surface)
        if SETTINGS_DEBUG_SHOW_VISIBLE_FOES:
          self._drawVisibleFoes(pygame, surface)
        self._drawDebugTextSurface(pygame, surface)

  #################
  #    Private    #
  # debug methods #
  #################

  def _drawVisibleFoes(self, pygame, surface):
    for o in self.observation.foes:
      pygame.draw.line(surface, (127,127,127), self.observation.loc, o[0:2])
  
  def _drawVisibleObjects(self, pygame, surface):
    for o in self.observation.objects:
      pygame.draw.line(surface, (255,255,255), self.observation.loc, o[0:2])

  def _drawCPDomination(self, pygame, surface):
    font = pygame.font.Font(pygame.font.get_default_font(), 10)
    for cp in self.observation.cps:
      txt = font.render(
        "%.2f" % (self.getDominationValue(cp[0:2]),), 
        True,
        (0,0,255)
      )
      surface.blit(txt, cp[0:2])
      txt2 = font.render(
        "%d" % (self.getHotspotValue(cp[0:2]),),
        True,
        (255,0,0)
      )
      surface.blit(txt2, (cp[0], cp[1]+10))
      pygame.draw.circle(surface, (255,0,0), cp[0:2], HOTSPOT_RANGE,2)

  def _drawBases(self, pygame, surface):
    if self.__class__.home_base is not None:
      font = pygame.font.Font(pygame.font.get_default_font(), 10)
      txt = font.render("@", False, (255,255,255))
      surface.blit(txt, self.__class__.home_base)
      surface.blit(txt, self.__class__.enemy_base)

  def _drawKnownAmmoSpots(self, pygame, surface):
    font = pygame.font.Font(pygame.font.get_default_font(), 10)
    for spot in self.__class__.ammoSpots:
      txt = font.render("*", False, (255,255,255))
      surface.blit(txt, spot)
    
  def _drawDebugTextSurface(self, pygame, surface):
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

  ##################################################

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
