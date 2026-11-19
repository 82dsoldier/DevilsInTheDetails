Scriptname DevilsJumpDoor extends ObjectReference
{A paratroop door on the C-130, shut by an invisible slab until the green light, and then only
for a jumper in power armor. The plane hangs over Sicily DZ at 1,000 ft: on the green light the
jumpmaster's script swaps this activator for the open doorway (DevilsC130DoorFrame) and Nate steps
out and falls for real.

No teleport: the game sets a moved actor down on the navmesh under its target, so once the DZ was
navmeshed a jump by MoveTo or SetPosition landed him at once (tested 2026-11-19).

Boarding is where power armor is really checked (the crew won't take a jumper without a rig).
This is the backstop for a player who climbs out of the armor in the cabin.

Goes on the C130_Door activator; both doors use it.}

ObjectReference Property JumpMarker Auto Const Mandatory
{DevilsSicilyJumpMarker, 1,000 ft above the landing ground: where a man stepping out of the
starboard door comes down. The plane and the stick's landings are laid out from it.}

Message Property NoRigMessage Auto Const Mandatory
{The jumpmaster's refusal, until he's voiced: "You're not going out my door without a rig."}

GlobalVariable Property GreenLight Auto Const Mandatory
{DevilsJumpGreenLight, set by the jumpmaster's script: 1 from the green light on.}

Event OnActivate(ObjectReference akActionRef)
	Actor player = Game.GetPlayer()
	If akActionRef != player
		Return
	EndIf
	If !player.IsInPowerArmor()
		NoRigMessage.Show()
	ElseIf GreenLight.GetValue() < 1
		Debug.Notification("Jumpmaster: Not till the green light, trooper!")
	Else
		Debug.Notification("Jumpmaster: GO! Step out the door!")
	EndIf
EndEvent
