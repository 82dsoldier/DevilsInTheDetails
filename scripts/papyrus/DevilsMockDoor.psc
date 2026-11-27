Scriptname DevilsMockDoor extends ObjectReference
{Jump school's mock door at Hanscom: the doorway, used as the plane's is. Sergeant Airborne runs
it from the sawdust with two commands only, "Stand in the door!" and "GO!" (the author,
2026-11-27). Using the doorway in power armor once he's taken Nate on (the quest's stage
StageReported) puts Nate in the door; a beat later comes "GO!", and using it again steps him
out onto the sawdust (LandingMarker). Then the sergeant critiques the exit, and the first time
the quest moves on to the tower (StageDone). Nate can go again whenever he likes.

His commands are notifications, as the jumpmaster's are, so they show with subtitles off.

Goes on the DevilsMockDoorExit activator (an invisible slab across the doorway).}

Quest Property MyQuest Auto Const Mandatory
{DevilsRecruiting ("All the Way").}

ObjectReference Property LandingMarker Auto Const Mandatory
{Where Nate comes down, on the sawdust 1.5 m out from the doorway, facing out.}

int Property StageReported = 15 Auto Const
{Sergeant Airborne has taken him on: the door is his.}

int Property StageDone = 20 Auto Const
{Out the mock door: the tower is next.}

int Property ObjectiveDoor = 15 Auto Const
int Property ObjectiveTower = 20 Auto Const

float Property GoDelay = 2.5 Auto Const
{From "Stand in the door!" to "GO!".}

float Property StallTime = 6.0 Auto Const
{How long he waits after "GO!" before he hurries Nate, and again before he gives up.}

int doorState = 0                          ; 0 waiting, 1 in the door, 2 GO given, 3 hurried
int TimerGo = 1
int TimerStall = 2

Event OnActivate(ObjectReference akActionRef)
	Actor player = Game.GetPlayer()
	If akActionRef != player
		Return
	EndIf
	If !MyQuest.GetStageDone(StageReported)
		Debug.Notification("Sergeant Airborne: Who said you could get in my door? Report to me first, recruit.")
	ElseIf !player.IsInPowerArmor()
		Debug.Notification("Sergeant Airborne: Where's your rig, recruit? Nobody goes out my door in his pajamas.")
	ElseIf doorState == 0
		doorState = 1
		Debug.Notification("Sergeant Airborne: Stand in the door!")
		StartTimer(GoDelay, TimerGo)
	ElseIf doorState == 1
		Debug.Notification("Sergeant Airborne: Did I say go? Wait for it!")
	Else
		StepOut(player)
	EndIf
EndEvent

Event OnTimer(int aiTimerID)
	If aiTimerID == TimerGo && doorState == 1
		doorState = 2
		Debug.Notification("Sergeant Airborne: GO!")
		StartTimer(StallTime, TimerStall)
	ElseIf aiTimerID == TimerStall && doorState == 2
		doorState = 3
		Debug.Notification("Sergeant Airborne: That's a door, recruit, not a window. GO!")
		StartTimer(StallTime, TimerStall)
	ElseIf aiTimerID == TimerStall && doorState == 3
		doorState = 0
		Debug.Notification("Sergeant Airborne: Get out of my door. Come back when you've grown a spine.")
	EndIf
EndEvent

Function StepOut(Actor player)
	doorState = 0
	CancelTimer(TimerStall)
	player.MoveTo(LandingMarker)
	Utility.Wait(1.5)
	int pick = Utility.RandomInt(0, 3)
	If pick == 0
		Debug.Notification("Sergeant Airborne: I didn't hear a count. Next time you count to four thousand, or you push the planet away till I get tired.")
	ElseIf pick == 1
		Debug.Notification("Sergeant Airborne: Chin on your chest, recruit! You want to eat your risers?")
	ElseIf pick == 2
		Debug.Notification("Sergeant Airborne: Hands on your reserve, not waving bye-bye to your mama!")
	Else
		Debug.Notification("Sergeant Airborne: That wasn't an exit, that was a fall. Hard exit, recruit!")
	EndIf
	If !MyQuest.GetStageDone(StageDone)
		Utility.Wait(3.0)
		Debug.Notification("Sergeant Airborne: ...Good enough. Tower's next.")
		MyQuest.SetStage(StageDone)
		MyQuest.SetObjectiveCompleted(ObjectiveDoor)
		MyQuest.SetObjectiveDisplayed(ObjectiveTower)
	EndIf
EndFunction
