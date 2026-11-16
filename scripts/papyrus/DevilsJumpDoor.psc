Scriptname DevilsJumpDoor extends ObjectReference
{A paratroop door on the C-130: out the door and 1,000 ft over Sicily DZ, in power armor only.

Boarding is where power armor is really checked (the crew won't take a jumper without a rig).
This is the backstop for a player who climbs out of the armor in the cabin.

Goes on the C130_Door activator; both doors use it.}

ObjectReference Property JumpMarker Auto Const Mandatory
{DevilsSicilyJumpMarker, 1,000 ft above the landing ground. Pointing this property at it is
what makes the marker persistent.}

Message Property NoRigMessage Auto Const Mandatory
{The jumpmaster's refusal, until he's voiced: "You're not going out my door without a rig."}

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

	jumping = True
	player.MoveTo(JumpMarker)
	; An actor moved to a marker may be set down on the ground below it. If so, put the player
	; back up in the air where the marker is.
	If player.GetPositionZ() < JumpMarker.GetPositionZ() - 500.0
		player.SetPosition(JumpMarker.GetPositionX(), JumpMarker.GetPositionY(), JumpMarker.GetPositionZ())
	EndIf
	jumping = False
EndEvent
