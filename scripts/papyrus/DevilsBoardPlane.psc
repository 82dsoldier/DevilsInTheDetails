Scriptname DevilsBoardPlane extends ObjectReference
{The open paratroop door of the Devils' C-130, parked on Hanscom's East Ramp: boarding the bird.

A jumper in power armor goes aboard: the player is moved into the cabin, which flies over
Sicily (a moved actor is set down on the navmesh under its target, and the cabin has
navmesh), and the Boarded global tells the jumpmaster the flight can start. Before this, the
jumpmaster watched the player's distance from a red light, and a save that kept the light's old
position (from before the plane moved) left him waiting forever (tested 2026-11-20).

Goes on the C130_BoardingDoor activator.}

ObjectReference Property CabinMarker Auto Const Mandatory
{DevilsC130CabinMarker: in the cabin's aisle, facing aft toward the jumpmaster.}

Message Property NoRigMessage Auto Const Mandatory
{The jumpmaster's refusal: "You're not going out my door without a rig."}

GlobalVariable Property Boarded Auto Const Mandatory
{DevilsBoarded: 1 when the player has boarded and the flight hasn't started; the jumpmaster
clears it as he starts.}

Event OnActivate(ObjectReference akActionRef)
	Actor player = Game.GetPlayer()
	If akActionRef != player
		Return
	EndIf
	If !player.IsInPowerArmor()
		NoRigMessage.Show()
		Return
	EndIf
	Boarded.SetValue(1)
	player.MoveTo(CabinMarker)
EndEvent
