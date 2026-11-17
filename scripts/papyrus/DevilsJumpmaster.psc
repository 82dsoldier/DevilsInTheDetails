Scriptname DevilsJumpmaster extends Actor
{The flight and the jumpmaster's commands: once the player is aboard, taxi, takeoff and cruise
(engine sound, the cabin shaking on the roll), then "Ten minutes!" to "GO!".

DevilsJumpmaster.psc is generated from DevilsJumpmaster.psc.in by scripts/make_jump_audio.py,
which times the lines to the audio: edit the .psc.in, not the .psc.

Goes on the jumpmaster's reference in the cabin (DevilsSicilyWorld, cell 4,-7), aft of the
starboard door.}

Sound Property commands_1 Auto Const Mandatory
{"Ten minutes!" through "Sound off for equipment check!" and the stick's OKs.}
Sound Property commands_2 Auto Const Mandatory
{"Six minutes!" through "Stand in the door!"}
Sound Property commands_3 Auto Const Mandatory
{"GO!"}
Message Property SoundOffMessage Auto Const Mandatory
{The player's sound-off: "All OK, jumpmaster!" (button 0) or "All OK, dumb bastard!" (button 1).}
GlobalVariable Property GreenLight Auto Const Mandatory
{DevilsJumpGreenLight: 1 from the green light on; the doors work only then.}
ObjectReference[] Property RedLights Auto Const
{The red jump lights (light references, Initially Disabled), one by each door.}
ObjectReference[] Property GreenLights Auto Const
{The green jump lights, the same.}
Sound Property EnginesIdle Auto Const Mandatory
{Looping: the engines at ground idle, while the stick boards and the plane taxis.}
Sound Property EnginesTakeoff Auto Const Mandatory
{One piece, TAKEOFF_LEN s (make_engine_audio.py): run-up, the roll, liftoff, the climb.}
Sound Property EnginesCruise Auto Const Mandatory
{Looping: the engines in flight.}
Sound Property EnginesCruiseDoors Auto Const Mandatory
{Looping: in flight with the jump doors open, the wind roaring in.}
Sound Property Hydraulics Auto Const Mandatory
{The pump closing the ramp and doors before takeoff; the doors shut HYD_CLOSED s in.}
Sound Property DoorOpenSound Auto Const Mandatory
{The loadmaster opening the jump doors: latch, rattle up the tracks, bang, wind.}
ObjectReference[] Property DoorsOpen Auto Const
{The jump doors slid up open (DevilsC130DoorOpen), one on each door: for boarding, and the jump.}
ObjectReference[] Property DoorsClosed Auto Const
{The jump doors shut (DevilsC130DoorClosed, Initially Disabled): for takeoff and the flight.}
Actor[] Property Stick Auto Const
{The Devils jumping with Nate (DevilsParatrooper, Initially Disabled): the outboard seats first
(OutboardCount of them), then the centerline. Each one's reference stands where he lines up after
"stand up", in the aisle facing aft.}
ObjectReference[] Property StickSeats Auto Const
{Each jumper's seat (DevilsC130SeatMarker), in the same order as Stick.}
Int Property OutboardCount = 4 Auto Const
Keyword Property SeatLink Auto Const Mandatory
{LinkCustom01: a jumper's link to his seat, where his sit package (DevilsSitOutboard or
DevilsSitInboard) sits him.}
GlobalVariable Property OutboardUp Auto Const Mandatory
{DevilsStickOutboardUp: the outboard sit package runs only while this is 0. Setting it to 1
stands them up, and they walk to their places in the aisle.}
GlobalVariable Property InboardUp Auto Const Mandatory
{DevilsStickInboardUp: the same for the centerline seats.}
ObjectReference[] Property StickLines Auto Const
{Each jumper's static line (DevilsC130StaticLineR on the starboard men, L on the port men,
Initially Disabled), in the same order as Stick: from "Hook up!" each is kept on its man, wherever
he actually stands, hooked to the anchor cable ahead of him.}
Float Property DoorRaise = 140.0 Auto Const
{How far the closed door slides up to be out of sight in the wall above the doorway.}
Float Property TaxiSeconds = 20.0 Auto Const
{From boarding to the run-up.}
Float Property CruiseSeconds = 30.0 Auto Const
{From reaching cruise to "Ten minutes!" (the flight, much shortened).}
ObjectReference[] Property DayLights Auto Const
{The cabin lights for a daytime jump: warm white.}
ObjectReference[] Property NightLights Auto Const
{The cabin lights for a night jump: dim red (Initially Disabled).}

Bool running = False
Int engine = 0                        ; the engine sound playing (its instance), 0 for none
Bool hooked = False                   ; the stick's static lines are on them

Event OnLoad()
	If running
		Return
	EndIf
	running = True
	; The plane hangs at jump height in Sicily. With no one aboard, he can load before its floor
	; does and fall, so he's disabled (a disabled actor doesn't fall) until the player is aboard,
	; then put back on his mark. Disabling and enabling fire OnUnload and OnLoad again; `running`
	; keeps this from starting twice.
	Disable()
	GreenLight.SetValue(0)
	SetLights(True, False)            ; red the whole way, till the green
	SetDoors(True)                    ; open for boarding
	Bool night = IsNight()            ; a night jump flies with the cabin dark and red
	SetAll(DayLights, !night)
	SetAll(NightLights, night)

	Cell plane = GetParentCell()
	While !PlayerAboard()
		If !plane.IsAttached()        ; the player went elsewhere
			MoveToMyEditorLocation()
			Enable()
			running = False
			Return
		EndIf
		Utility.Wait(1.0)
	EndWhile
	MoveToMyEditorLocation()
	Enable()
	SeatStick()                       ; already aboard and seated: Nate boards last
	Fly()                             ; taxi, takeoff, climb, the flight

	; The loadmaster opens the doors as the jumpmaster starts.
	CallFunctionNoWait("LoadmasterOpensDoors", new Var[0])
	Utility.Wait(0.5)
	Play_commands_1()
	; Over the engines the jumpmaster can't hear a word of it, only that you shouted.
	If SoundOffMessage.Show() == 1
		Debug.Notification("The jumpmaster nods. Somebody behind you snorts.")
	Else
		Debug.Notification("The jumpmaster nods.")
	EndIf
	Utility.Wait(1.5)

	Play_commands_2()
	Utility.Wait(Utility.RandomFloat(3.0, 6.0))
	SetLights(False, True)
	GreenLight.SetValue(1)
	Play_commands_3()

	; Out the door, the plane flies on without you.
	While PlayerAboard()
		Utility.Wait(0.5)
	EndWhile
	ClearStick()                      ; they followed him out
	Crossfade(engine, 0, 1.5)
	engine = 0
	running = False
EndEvent

Event OnUnload()
	GreenLight.SetValue(0)
	If engine > 0
		Sound.StopInstance(engine)
		engine = 0
	EndIf
	ClearStick()                      ; left mid-flight: no one waiting to fall on the next load
EndEvent

Function Fly()
	{From boarding to cruise: the engines idle while the plane taxis, run up, roar down the runway
	(the cabin shaking, harder as it gathers speed), and settle once it's climbed. The waits follow
	the takeoff piece's timings in make_engine_audio.py: RUNUP 4, BRAKES_OFF 14, LIFTOFF 38,
	CLIMBED 53, TAKEOFF_LEN 56.}
	engine = EnginesIdle.Play(Self)
	Utility.Wait(TaxiSeconds)
	Hydraulics.Play(Self)             ; the ramp and doors closing, right before takeoff
	Utility.Wait(4.6)
	SlideDoorsClosed(4.2)             ; down as the pump labours, home at HYD_CLOSED (9 s)
	Utility.Wait(0.2)
	Utility.Wait(1.5)

	Int next = EnginesTakeoff.Play(Self)
	Crossfade(engine, next, 2.0)      ; 0 to 2 s into the piece
	engine = next
	Utility.Wait(12.0)                ; brakes off at 14
	Int i = 0
	While i < 24                      ; the roll, 14 to 38
		Game.ShakeCamera(None, 0.03 + 0.005 * i, 1.0)
		Utility.Wait(1.0)
		i += 1
	EndWhile
	Utility.Wait(15.0)                ; climbed by 53
	next = EnginesCruise.Play(Self)
	Crossfade(engine, next, 2.0)
	engine = next
	Utility.Wait(CruiseSeconds)
EndFunction

Function SeatStick()
	{Every jumper in his seat. They're disabled until now so none can load before the floor and
	fall, as the jumpmaster could.}
	If !Stick
		Return
	EndIf
	OutboardUp.SetValue(0)
	InboardUp.SetValue(0)
	Int i = 0
	While i < Stick.Length
		Stick[i].SetLinkedRef(StickSeats[i], SeatLink)
		Stick[i].Enable()
		i += 1
	EndWhile
	i = 0
	While i < Stick.Length
		Int tries = 0
		While !Stick[i].Is3DLoaded() && tries < 20
			Utility.Wait(0.1)
			tries += 1
		EndWhile
		Stick[i].SnapIntoInteraction(StickSeats[i])
		i += 1
	EndWhile
EndFunction

Function StandUp(Bool outboard)
	{"Outboard personnel, stand up!" or "Inboard...": that half of the stick gets up and lines up
	in the aisles, facing aft.}
	If !Stick
		Return
	EndIf
	If outboard
		OutboardUp.SetValue(1)
	Else
		InboardUp.SetValue(1)
	EndIf
	Int i = 0
	While i < Stick.Length
		If (i < OutboardCount) == outboard
			Stick[i].EvaluatePackage()
		EndIf
		i += 1
	EndWhile
EndFunction

Function HookUp()
	{"Hook up!": the stick snaps their static lines to the anchor cables.}
	If !StickLines || !Stick
		Return
	EndIf
	hooked = True
	Int i = 0
	While i < StickLines.Length && i < Stick.Length
		PlaceLine(i)
		StickLines[i].Enable()
		i += 1
	EndWhile
	CallFunctionNoWait("FollowStick", new Var[0])
EndFunction

Function FollowStick()
	{Keeps each static line on its man while the stick is hooked up, if he's jostled or shuffles.}
	While hooked
		Utility.Wait(0.25)
		Int i = 0
		While hooked && i < StickLines.Length && i < Stick.Length
			PlaceLine(i)
			i += 1
		EndWhile
	EndWhile
EndFunction

Function PlaceLine(Int i)
	{The line's model is in its man's frame, facing aft: put it where he stands. Turned with the
	cabin, not with him, so the hook stays on the cable however he turns his shoulders.}
	Actor man = Stick[i]
	ObjectReference line = StickLines[i]
	Float px = man.GetPositionX()
	Float py = man.GetPositionY()
	Float pz = man.GetPositionZ()
	If Math.Abs(line.GetPositionX() - px) + Math.Abs(line.GetPositionY() - py) + Math.Abs(line.GetPositionZ() - pz) > 1.0
		line.SetPosition(px, py, pz)
		line.SetAngle(0.0, 0.0, 180.0)
	EndIf
EndFunction

Function ClearStick()
	{Out the door after Nate: gone from the plane, and back on their marks for next time.}
	hooked = False
	SetAll(StickLines, False)
	If !Stick
		Return
	EndIf
	Int i = 0
	While i < Stick.Length
		Stick[i].Disable()
		Stick[i].MoveToMyEditorLocation()
		i += 1
	EndWhile
EndFunction

Function LoadmasterOpensDoors()
	{Run alongside the commands: the doors rattle up their tracks, and the wind comes in.}
	Debug.Notification("The loadmaster opens the jump doors.")
	DoorOpenSound.Play(Self)
	Utility.Wait(0.4)                 ; DOOR_SLIDE: unlatched, it starts up its tracks
	SlideDoorsOpen(2.8)               ; and bangs to the top at DOOR_UP (3.2 s)
	Int next = EnginesCruiseDoors.Play(Self)
	Crossfade(engine, next, 1.5)
	engine = next
EndFunction

Function SetDoors(Bool open)
	{At once, no sliding: open for boarding.}
	SetAll(DoorsOpen, open)
	SetAll(DoorsClosed, !open)
	Int i = 0
	While DoorsClosed && i < DoorsClosed.Length
		DoorsClosed[i].MoveToMyEditorLocation()
		i += 1
	EndWhile
EndFunction

Function SlideDoorsClosed(Float seconds)
	{Each door comes down out of the wall above the doorway into place, over `seconds`.}
	If !DoorsClosed
		Return
	EndIf
	Int i = 0
	While i < DoorsClosed.Length
		ObjectReference d = DoorsClosed[i]
		d.MoveToMyEditorLocation()
		d.SetPosition(d.GetPositionX(), d.GetPositionY(), d.GetPositionZ() + DoorRaise)
		d.Enable()
		i += 1
	EndWhile
	SetAll(DoorsOpen, False)
	i = 0
	While i < DoorsClosed.Length
		ObjectReference d = DoorsClosed[i]
		Int tries = 0
		While !d.Is3DLoaded() && tries < 20
			Utility.Wait(0.05)
			tries += 1
		EndWhile
		d.TranslateTo(d.GetPositionX(), d.GetPositionY(), d.GetPositionZ() - DoorRaise, \
			d.GetAngleX(), d.GetAngleY(), d.GetAngleZ(), DoorRaise / seconds)
		i += 1
	EndWhile
	Utility.Wait(seconds)
EndFunction

Function SlideDoorsOpen(Float seconds)
	{Each door slides up out of the doorway into the wall above it over `seconds`, and is then
	shown lying open on its tracks against the upper wall.}
	If !DoorsClosed
		Return
	EndIf
	Int i = 0
	While i < DoorsClosed.Length
		ObjectReference d = DoorsClosed[i]
		d.TranslateTo(d.GetPositionX(), d.GetPositionY(), d.GetPositionZ() + DoorRaise, \
			d.GetAngleX(), d.GetAngleY(), d.GetAngleZ(), DoorRaise / seconds)
		i += 1
	EndWhile
	Utility.Wait(seconds)
	SetDoors(True)
EndFunction

Function Crossfade(Int fromSound, Int toSound, Float seconds)
	{Fades one sound instance out and another in (either can be 0, for none), then stops the first.}
	If toSound > 0
		Sound.SetInstanceVolume(toSound, 0.0)
	EndIf
	Int steps = 10
	Int i = 1
	While i <= steps
		Float v = (i as Float) / steps
		If toSound > 0
			Sound.SetInstanceVolume(toSound, v)
		EndIf
		If fromSound > 0
			Sound.SetInstanceVolume(fromSound, 1.0 - v)
		EndIf
		Utility.Wait(seconds / steps)
		i += 1
	EndWhile
	If fromSound > 0
		Sound.StopInstance(fromSound)
	EndIf
EndFunction

Bool Function PlayerAboard()
	{Within 1,500 units of the first red light, by the doors: anywhere in the cabin, and nowhere
	on the ground 350 m below. Measured from a light, not from him, since he may have fallen.}
	If !RedLights
		Return True
	EndIf
	ObjectReference mark = RedLights[0]
	Actor player = Game.GetPlayer()
	Float dx = player.GetPositionX() - mark.GetPositionX()
	Float dy = player.GetPositionY() - mark.GetPositionY()
	Float dz = player.GetPositionZ() - mark.GetPositionZ()
	Return dx * dx + dy * dy + dz * dz < 1500.0 * 1500.0
EndFunction

Bool Function IsNight()
	{From 8 in the evening to 6 in the morning, game time.}
	Float days = Utility.GetCurrentGameTime()
	Float hour = (days - Math.Floor(days)) * 24.0
	Return hour >= 20.0 || hour < 6.0
EndFunction

Function SetLights(Bool red, Bool green)
	SetAll(RedLights, red)
	SetAll(GreenLights, green)
EndFunction

Function SetAll(ObjectReference[] refs, Bool on)
	If !refs
		Return
	EndIf
	Int i = 0
	While i < refs.Length
		If on
			refs[i].Enable()
		Else
			refs[i].Disable()
		EndIf
		i += 1
	EndWhile
EndFunction

; --- Generated by make_jump_audio.py: each piece played, its lines shown as they're said ---

Function Play_commands_1()
	Int id = commands_1.Play(Self)
	Utility.Wait(0.30)
	Debug.Notification("Jumpmaster (both hands up, all ten fingers spread): Ten minutes!")
	Utility.Wait(2.50)
	Debug.Notification("Jumpmaster (both arms out toward the stick): Get ready!")
	Utility.Wait(2.22)
	Debug.Notification("Jumpmaster (arms to the outboard seats, palms up, raised): Outboard personnel, stand up!")
	Utility.Wait(1.80)
	StandUp(True)
	Utility.Wait(3.27)
	Debug.Notification("Jumpmaster (arms to the centre seats, palms up, raised): Inboard personnel, stand up!")
	Utility.Wait(1.76)
	StandUp(False)
	Utility.Wait(3.20)
	Debug.Notification("Jumpmaster (arm overhead, finger crooked like a hook, pumping): Hook up!")
	Utility.Wait(0.28)
	HookUp()
	Utility.Wait(1.56)
	Debug.Notification("Jumpmaster (OK rings with both hands, drawn to his eyes): Check static lines!")
	Utility.Wait(3.29)
	Debug.Notification("Jumpmaster (fingertips tapping his chest): Check equipment!")
	Utility.Wait(2.59)
	Debug.Notification("Jumpmaster (hands cupped behind his ears): Sound off for equipment check!")
	Utility.Wait(4.16)
	Debug.Notification("The stick: OK! OK! OK!")
	Utility.Wait(2.37)
EndFunction

Function Play_commands_2()
	Int id = commands_2.Play(Self)
	Utility.Wait(0.30)
	Debug.Notification("Jumpmaster (six fingers up): Six minutes!")
	Utility.Wait(2.74)
	Debug.Notification("Jumpmaster (one finger up): One minute!")
	Utility.Wait(2.21)
	Debug.Notification("Jumpmaster (thumb and forefinger an inch apart): Thirty seconds!")
	Utility.Wait(2.88)
	Debug.Notification("Jumpmaster (points the first jumper into the door): Stand in the door!")
	Utility.Wait(1.09)
EndFunction

Function Play_commands_3()
	Int id = commands_3.Play(Self)
	Utility.Wait(0.30)
	Debug.Notification("Jumpmaster: Go!")
	Utility.Wait(0.49)
EndFunction

