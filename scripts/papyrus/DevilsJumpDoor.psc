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
	; not in the air (tested: with the DZ navmeshed he no longer fell). Wait till the move has
	; happened (read straight away, his height was still the plane's, the marker's own), then put
	; him back up where the marker is.
	Int tries = 0
	While tries < 40 && Math.Abs(player.GetPositionX() - JumpMarker.GetPositionX()) > 500.0
		Utility.Wait(0.05)
		tries += 1
	EndWhile
	If player.GetPositionZ() < JumpMarker.GetPositionZ() - 500.0
		player.SetPosition(JumpMarker.GetPositionX(), JumpMarker.GetPositionY(), JumpMarker.GetPositionZ())
	EndIf
	jumping = False
EndEvent
