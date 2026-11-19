Scriptname DevilsJumpDoor extends ObjectReference
{A paratroop door on the C-130: out the door and 1,000 ft over Sicily DZ, in power armor only,
and only on the green light.

Boarding is where power armor is really checked (the crew won't take a jumper without a rig).
This is the backstop for a player who climbs out of the armor in the cabin.

Goes on the C130_Door activator; both doors use it.}

ObjectReference Property JumpMarker Auto Const Mandatory
{DevilsSicilyJumpMarker, 1,000 ft above the landing ground. Pointing this property at it is
what makes the marker persistent.}

Message Property NoRigMessage Auto Const Mandatory
{The jumpmaster's refusal, until he's voiced: "You're not going out my door without a rig."}

GlobalVariable Property GreenLight Auto Const Mandatory
{DevilsJumpGreenLight, set by the jumpmaster's script: 1 from the green light on.}

Bool jumping = False

Event OnActivate(ObjectReference akActionRef)
	Actor player = Game.GetPlayer()
	If akActionRef != player || jumping
		Return
	EndIf
	If !player.IsInPowerArmor()
		NoRigMessage.Show()
		Return
	EndIf
	If GreenLight.GetValue() < 1
		Debug.Notification("Jumpmaster: Not till the green light, trooper!")
		Return
	EndIf

	jumping = True
	player.MoveTo(JumpMarker)
	; MoveTo sets an actor down on the navmesh under the marker, if there is any: on the ground,
	; not in the air (tested: with the DZ navmeshed he no longer fell). It does so a moment after
	; the move, as he loads in, while his height still reads the marker's (tested: a check straight
	; after the move, or once he'd arrived, missed it). So watch him for 2 seconds: dropping
	; more than 15,000 units (200 m) in the first 2 s is the snap, not the fall (the whole 21,000 takes
	; 4-5 s), and he's put back up where the marker is.
	Float top = JumpMarker.GetPositionZ()
	Int tries = 0
	Bool snapped = False
	While tries < 20 && !snapped              ; 2 s: a real fall is 4,000 units down by then
		Utility.Wait(0.1)
		If player.GetPositionZ() < top - 15000.0
			player.SetPosition(JumpMarker.GetPositionX(), JumpMarker.GetPositionY(), top)
			snapped = True
		EndIf
		tries += 1
	EndWhile
	jumping = False
EndEvent
