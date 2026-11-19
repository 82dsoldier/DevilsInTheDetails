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
{The jump doors shut: each door's five panels (DevilsC130DoorPanel0-4, Initially Disabled), for
takeoff and the flight. They slide along the door's track (DevilsC130DoorPanel).}

CustomEvent DoorsStow
CustomEvent DoorsSlide
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
ObjectReference[] Property StickStands Auto Const
{Each jumper's mark in line (an XMarkerHeading on his own reference's spot, facing aft), in the
same order as Stick. Up, he walks back to his spot; nearly there, he's set on his mark and held
(restrained), so his hook is on the cable and no one shoves him off it.}
Float Property SettleDistance = 45.0 Auto Const
{How near his mark (game units) a jumper walks before he's set on it.}
Float Property SettleSeconds = 10.0 Auto Const
{The longest he's given to get there before he's set on it anyway.}
Float Property HoldDegrees = 3.0 Auto Const
{Settled, how far he may turn from facing aft before he's put back.}
Float Property HoldDistance = 4.0 Auto Const
{Settled, how far (game units) he may drift off his mark before he's put back.}
Armor Property StaticLineRight Auto Const Mandatory
{DevilsStaticLineRight: a hooked-up static line, worn (body slot 56), over the right shoulder to
the anchor cable ahead of him. The starboard men's: facing aft, their inboard shoulder.}
Armor Property StaticLineLeft Auto Const Mandatory
{DevilsStaticLineLeft: the same over the left shoulder, for the port men.}
ObjectReference Property Tarmac Auto Const Mandatory
{DevilsC130Tarmac: the apron under the plane, seen out of the open doors on the ground (the plane
hangs at jump height, so otherwise it's all sky out there); gone as the doors close for takeoff.}
Idle Property SignalHookUp Auto Const Mandatory
{DevilsJMSignalHookUp: his "Hook up!" signal (make_jm_signals.py), arm overhead, finger hooked,
pumping; a dynamic idle like the vanilla BOS_Salute.}
Idle Property SignalTenMinutes Auto Const Mandatory
{DevilsJMSignalTenMinutes: "Ten minutes!", both hands out in front, fingers splayed.}
Idle Property SignalGetReady Auto Const Mandatory
{DevilsJMSignalGetReady: "Get ready!", the same, fingers together, hands tipped forward 45 degrees.}
Idle Property SignalStandUp Auto Const Mandatory
{DevilsJMSignalStandUp: "Outboard/Inboard personnel, stand up!", both arms out, palms up, raised.}
Idle Property SignalCheckEquipment Auto Const Mandatory
{DevilsJMSignalCheckEquipment: "Check equipment!", both hands' fingertips tapping his chest.}
Float Property SignalSeconds = 3.0 Auto Const
{How long a signal takes (the animations are 2.8 s).}
Armor Property StaticLineJM Auto Const Mandatory
{DevilsStaticLineJM: the jumpmaster's own static line (slot 56), hooked up before he starts the
commands (the author): over his left shoulder to the starboard cable ahead of him, built for
where he stands (on the ramp aft of the door, facing forward).}
Armor Property JumpKit Auto Const Mandatory
{DevilsJumpKit: each man's parachutes, worn (body slot 57): T-10C main, harness, T-10R reserve.
He wears it from boarding.}
Armor Property GearSeated Auto Const Mandatory
{DevilsJumpGearSeated: his ALICE ruck and weapons case as he sits (body slot 58): the ruck in his
lap, the case tipped forward clear of the seat.}
Armor Property GearStanding Auto Const Mandatory
{DevilsJumpGearStanding: the same as he stands (slot 58): the ruck right under the reserve, the
case straight down his left side. He changes into it as he gets up.}
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
Bool holding = False                  ; the stick is held on their marks (SettleHalf)
Bool hooked = False                   ; "Hook up!" has been given
Bool[] up                             ; each man (by Stick's order) is out of his seat

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
	Int p = 0
	While DoorsClosed && p < DoorsClosed.Length
		(DoorsClosed[p] as DevilsC130DoorPanel).Listen(Self)
		p += 1
	EndWhile
	Tarmac.Enable()                   ; on the ground
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
	DressJumpmaster()                 ; he jumps too
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
	Tarmac.Disable()                  ; the doors long shut: no one sees the ground go
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
	hooked = False
	up = new Bool[Stick.Length]
	Int i = 0
	While i < Stick.Length
		Stick[i].SetRestrained(False)
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
		Dress(i)
		Stick[i].SnapIntoInteraction(StickSeats[i])
		i += 1
	EndWhile
EndFunction

Function StandUp(Bool outboard)
	{"Outboard personnel, stand up!" or "Inboard...": that half of the stick gets up and lines up
	in the aisles, facing aft, each settled on his mark.}
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
	Var[] args = new Var[1]
	args[0] = outboard
	CallFunctionNoWait("SettleHalf", args)
EndFunction

Function SettleHalf(Bool outboard)
	{Watch that half walk to their spots; as each comes near his mark (or runs out of time), set
	him on it, facing aft, and hold him there.}
	If !StickStands
		Return
	EndIf
	Float waited = 0.0
	Bool[] settled = new Bool[Stick.Length]
	Int left = 1
	While left > 0
		left = 0
		Int i = 0
		While i < Stick.Length
			Actor man = Stick[i]
			If (i < OutboardCount) == outboard && !up[i] && man.GetSitState() == 0
				up[i] = True                     ; out of his seat: his ruck and case as he stands
				Dress(i)
			EndIf
			If (i < OutboardCount) == outboard && !settled[i]
				If man.GetSitState() == 0 && (man.GetDistance(StickStands[i]) < SettleDistance || waited >= SettleSeconds)
					man.MoveTo(StickStands[i])
					man.SetRestrained(True)
					man.SetHeadTracking(False)   ; eyes front: no turning to look about
					settled[i] = True
				Else
					left += 1
				EndIf
			EndIf
			i += 1
		EndWhile
		If waited >= SettleSeconds + 5.0     ; still seated after all that: leave him be
			left = 0
		Else
			Utility.Wait(0.25)
			waited += 0.25
		EndIf
	EndWhile

	; Hold them there: anyone who turns or drifts off his mark is put back on it, so his hook
	; stays on the cable. Until they follow Nate out (ClearStick ends `holding`).
	holding = True
	While holding
		Int i = 0
		While i < Stick.Length && holding
			If settled[i]
				Actor man = Stick[i]
				Float turn = Math.Abs(man.GetAngleZ() - StickStands[i].GetAngleZ())
				If turn > 180.0
					turn = 360.0 - turn
				EndIf
				If turn > HoldDegrees || man.GetDistance(StickStands[i]) > HoldDistance
					man.MoveTo(StickStands[i])
				EndIf
			EndIf
			i += 1
		EndWhile
		Utility.Wait(0.5)
	EndWhile
EndFunction

Function HookUp()
	{"Hook up!": the stick snaps their static lines to the anchor cables.}
	If !Stick
		Return
	EndIf
	hooked = True
	Int i = 0
	While i < Stick.Length
		Dress(i)
		i += 1
	EndWhile
EndFunction

Armor Function LineFor(Int i)
	{His static line: over the inboard shoulder, his right on the starboard side.}
	If i % 4 < 2                      ; Stick's order: outboard stbd 1-2, port 1-2; inboard the same
		Return StaticLineRight
	EndIf
	Return StaticLineLeft
EndFunction

Function Dress(Int i)
	{Everything he wears where he is now: his parachutes, his ruck and case as he sits or stands,
	and his static line once hooked up. Giving him an item took off what the script had put on
	(tested: the line took the kit off), so it all goes into his inventory first, then on.}
	Actor man = Stick[i]
	Armor gear = GearSeated
	Armor other = GearStanding
	If up && up[i]
		gear = GearStanding
		other = GearSeated
	EndIf
	Armor line = None
	If hooked
		line = LineFor(i)
	EndIf
	man.RemoveItem(other, -1, True)
	If man.GetItemCount(JumpKit) == 0
		man.AddItem(JumpKit, 1, True)
	EndIf
	If man.GetItemCount(gear) == 0
		man.AddItem(gear, 1, True)
	EndIf
	If line && man.GetItemCount(line) == 0
		man.AddItem(line, 1, True)
	EndIf
	man.EquipItem(JumpKit, True, True)
	man.EquipItem(gear, True, True)
	If line
		man.EquipItem(line, True, True)
	EndIf
EndFunction

Function Unhook(Actor man)
	man.RemoveItem(StaticLineRight, -1, True)
	man.RemoveItem(StaticLineLeft, -1, True)
EndFunction

Function DressJumpmaster()
	{The jumpmaster jumps too (the author): the same kit as the stick, his ruck and case as he
	stands, for he stands the whole flight. Everything into his inventory first, then on.}
	Int tries = 0
	While !Is3DLoaded() && tries < 20
		Utility.Wait(0.1)
		tries += 1
	EndWhile
	If GetItemCount(JumpKit) == 0
		AddItem(JumpKit, 1, True)
	EndIf
	If GetItemCount(GearStanding) == 0
		AddItem(GearStanding, 1, True)
	EndIf
	If GetItemCount(StaticLineJM) == 0
		AddItem(StaticLineJM, 1, True)
	EndIf
	EquipItem(JumpKit, True, True)
	EquipItem(GearStanding, True, True)
	EquipItem(StaticLineJM, True, True)
	CallFunctionNoWait("HoldJumpmaster", new Var[0])
EndFunction

Function Signal(Idle sig)
	{His hand signal, as he starts the command; the commands carry on meanwhile.}
	Var[] args = new Var[1]
	args[0] = sig
	CallFunctionNoWait("GiveSignal", args)
EndFunction

Function GiveSignal(Idle sig)
	{Held (restrained) he may not animate: let him go for the signal, then hold him again.}
	SetRestrained(False)
	PlayIdle(sig)
	Utility.Wait(SignalSeconds)
	If running
		SetRestrained(True)
	EndIf
EndFunction

Function HoldJumpmaster()
	{Hooked up, he stays put so his hook stays on the cable: no turning to look about, and if he
	turns or drifts off his spot he's put back on it. For the flight (`running`).}
	SetRestrained(True)
	SetHeadTracking(False)
	Float heading = GetAngleZ()           ; just put on his editor spot (OnLoad)
	Float px = GetPositionX()
	Float py = GetPositionY()
	While running && Is3DLoaded()
		Float turn = Math.Abs(GetAngleZ() - heading)
		If turn > 180.0
			turn = 360.0 - turn
		EndIf
		Float dx = GetPositionX() - px
		Float dy = GetPositionY() - py
		If turn > HoldDegrees || Math.Sqrt(dx * dx + dy * dy) > HoldDistance
			MoveToMyEditorLocation()
		EndIf
		Utility.Wait(0.5)
	EndWhile
	SetRestrained(False)
	SetHeadTracking(True)
EndFunction

Function ClearStick()
	{Out the door after Nate: gone from the plane, and back on their marks for next time.}
	holding = False
	If !Stick
		Return
	EndIf
	Int i = 0
	While i < Stick.Length
		Unhook(Stick[i])
		Stick[i].RemoveItem(JumpKit, -1, True)
		Stick[i].RemoveItem(GearSeated, -1, True)
		Stick[i].RemoveItem(GearStanding, -1, True)
		Stick[i].SetRestrained(False)
		Stick[i].SetHeadTracking(True)
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
		DoorsClosed[i].StopTranslation()
		DoorsClosed[i].MoveToMyEditorLocation()
		i += 1
	EndWhile
EndFunction

Function SlideDoorsClosed(Float seconds)
	{The door comes down off the ceiling, round the track and into the doorway, over `seconds`:
	its panels are shown where it lies open, the open door hidden, and they slide together.}
	If !DoorsClosed
		Return
	EndIf
	SendCustomEvent("DoorsStow", new Var[0])
	Utility.Wait(0.4)                 ; all of them shown where the open door is
	SetAll(DoorsOpen, False)
	Var[] args = new Var[2]
	args[0] = False
	args[1] = seconds - 0.4
	SendCustomEvent("DoorsSlide", args)
	Utility.Wait(seconds - 0.4)
EndFunction

Function SlideDoorsOpen(Float seconds)
	{The door slides up out of the doorway and round its track to lie under the ceiling over
	`seconds`, then is swapped for the open door (the same shape, there).}
	If !DoorsClosed
		Return
	EndIf
	Var[] args = new Var[2]
	args[0] = True
	args[1] = seconds
	SendCustomEvent("DoorsSlide", args)
	Utility.Wait(seconds + 0.2)
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
	Signal(SignalTenMinutes)
	Utility.Wait(1.00)
	Debug.Notification("Jumpmaster: Ten minutes!")
	Utility.Wait(3.00)
	Signal(SignalGetReady)
	Utility.Wait(1.00)
	Debug.Notification("Jumpmaster: Get ready!")
	Utility.Wait(3.00)
	Signal(SignalStandUp)
	Utility.Wait(1.00)
	Debug.Notification("Jumpmaster: Outboard personnel, stand up!")
	Utility.Wait(1.80)
	StandUp(True)
	Utility.Wait(3.27)
	Signal(SignalStandUp)
	Utility.Wait(1.00)
	Debug.Notification("Jumpmaster: Inboard personnel, stand up!")
	Utility.Wait(1.76)
	StandUp(False)
	Utility.Wait(3.20)
	Signal(SignalHookUp)
	Utility.Wait(1.00)
	Debug.Notification("Jumpmaster: Hook up!")
	Utility.Wait(0.28)
	HookUp()
	Utility.Wait(2.72)
	Signal(SignalHookUp)
	Utility.Wait(1.00)
	Debug.Notification("Jumpmaster: Check static lines!")
	Utility.Wait(3.29)
	Signal(SignalCheckEquipment)
	Utility.Wait(1.00)
	Debug.Notification("Jumpmaster: Check equipment!")
	Utility.Wait(3.00)
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

