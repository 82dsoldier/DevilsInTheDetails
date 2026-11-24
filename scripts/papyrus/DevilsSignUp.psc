Scriptname DevilsSignUp extends TopicInfo Const
{On SSG Brannock's sign-up lines (officer or enlisted): when the line ends, Nate is signed up.
Records which (DevilsNateRank: 1 officer, 2 enlisted, a corporal), sets the quest's stage
(its log entry), and shows the objective that says what's next, so the player sees the story
move on (the author, 2026-11-24).}

Quest Property MyQuest Auto Const Mandatory
{The quest: DevilsRecruiting ("All the Way").}

GlobalVariable Property Rank Auto Const Mandatory
{DevilsNateRank.}

float Property RankValue Auto Const Mandatory
{1 for an officer, 2 for enlisted.}

int Property StageToSet = 10 Auto Const
{Signed up.}

int Property ObjectiveToShow = 10 Auto Const
{Report to jump school.}

Event OnEnd(ObjectReference akSpeakerRef, bool abHasBeenSaid)
	Rank.SetValue(RankValue)
	MyQuest.SetStage(StageToSet)
	MyQuest.SetObjectiveDisplayed(ObjectiveToShow)
EndEvent
