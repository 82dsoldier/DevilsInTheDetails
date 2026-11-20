Scriptname DevilsBoardPlane extends ObjectReference
{The open paratroop door of the Devils' C-130, parked on Hanscom's East Ramp: boarding the bird.

It's a load door, linked to a hidden door under the cabin floor over Sicily, its marker in the
aisle: the game's own door transition puts the player exactly there. Moving him by script
(MoveTo, and SetPosition alike) set him on the ground's navmesh 300 m below the cabin, however
long the cabin had been loaded (tested 2026-11-20).

A jumper in power armor goes aboard, and the Boarded global tells the jumpmaster the flight
can start (he used to watch the player's distance from a red light, and a save that kept the
light's old position left him waiting forever). Anyone else gets the jumpmaster's refusal.

Goes on the DevilsC130LoadDoor door.}

Message Property NoRigMessage Auto Const Mandatory
{The jumpmaster's refusal: "You're not going out my door without a rig."}

GlobalVariable Property Boarded Auto Const Mandatory
{DevilsBoarded: 1 when the player has boarded and the flight hasn't started; the jumpmaster
clears it as he starts.}

Event OnLoad()
	BlockActivation(True)             ; the rig check first; then the door does its own thing
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
	Boarded.SetValue(1)
	Activate(player, True)            ; the door's own activation: through to the cabin
EndEvent
