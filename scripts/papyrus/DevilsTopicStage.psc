Scriptname DevilsTopicStage extends TopicInfo Const
{On a line: when it ends, set the quest's stage, and complete one objective and show the next,
so the player sees the story move on. First used on Sergeant Airborne's first greeting
(2026-11-27): Nate has reported to jump school, and the mock door is next.}

Quest Property MyQuest Auto Const Mandatory
{The quest: DevilsRecruiting ("All the Way").}

int Property StageToSet Auto Const Mandatory

int Property ObjectiveToComplete = -1 Auto Const
{-1 for none.}

int Property ObjectiveToShow = -1 Auto Const
{-1 for none.}

Event OnEnd(ObjectReference akSpeakerRef, bool abHasBeenSaid)
	If MyQuest.GetStageDone(StageToSet)
		Return
	EndIf
	MyQuest.SetStage(StageToSet)
	If ObjectiveToComplete >= 0
		MyQuest.SetObjectiveCompleted(ObjectiveToComplete)
	EndIf
	If ObjectiveToShow >= 0
		MyQuest.SetObjectiveDisplayed(ObjectiveToShow)
	EndIf
EndEvent
