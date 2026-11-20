Scriptname DevilsJumpExit extends ObjectReference
{The open paratroop door from the green light on: a load door out of the cabin (an interior
cell) to the exit point 1,000 ft over Sicily DZ, where the jumper falls. The jumpmaster's
script enables both on the green light (SetDoorways), in place of the closed doors' slabs.

A load door's teleport puts the player where its marker is, in the air (tested 2026-11-20);
moving him by script set him on the ground's navmesh instead.

Goes on the DevilsC130JumpExit door; both doors use it.}

Message Property NoRigMessage Auto Const Mandatory
{The jumpmaster's refusal: "You're not going out my door without a rig."}

Event OnLoad()
	BlockActivation(True)             ; the rig check first
EndEvent

Event OnActivate(ObjectReference akActionRef)
	Actor player = Game.GetPlayer()
	If akActionRef != player
		Return
	EndIf
	If !player.IsInPowerArmor()
		NoRigMessage.Show()
		Return
	EndIf
	Activate(player, True)            ; out the door
EndEvent
