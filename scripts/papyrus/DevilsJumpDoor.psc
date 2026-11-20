Scriptname DevilsJumpDoor extends ObjectReference
{A paratroop door on the C-130, shut by an invisible slab, and the way out: from the green
light, a jumper in power armor using it goes out through its load door (ExitDoor) to the air
over Sicily DZ, and falls. The cabin is an interior; a load door's teleport puts him in the air
(on the navmesh patch floating there), where script moves set him on the ground.

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

ObjectReference Property ExitDoor Auto Const
{This doorway's way out (DevilsC130JumpExit): a load door to the exit point over Sicily, with no
collision of its own (the player's prompt is this slab's, the whole flight), enabled by the
jumpmaster's script from the green light. Its exit swapped in for the slab at the green light
gave no prompt (tested 2026-11-20).}

Event OnActivate(ObjectReference akActionRef)
	Actor player = Game.GetPlayer()
	If akActionRef != player
		Return
	EndIf
	If !player.IsInPowerArmor()
		NoRigMessage.Show()
	ElseIf GreenLight.GetValue() < 1
		Debug.Notification("Jumpmaster: Not till the green light, trooper!")
	ElseIf !ExitDoor || ExitDoor.IsDisabled()
		Debug.Notification("Jumpmaster: GO! Step out the door!")
	Else
		ExitDoor.Activate(player, True)   ; out: the load door's teleport, to the air over the DZ
	EndIf
EndEvent
