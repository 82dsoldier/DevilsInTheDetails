# Decision tree

The player's choices in The Devils in the Details, drawn from [DESIGN.md](DESIGN.md). Red boxes are
the ones that turn a faction hostile for good; dashed boxes are still undecided.

## 1. Boston to the drop zone

```mermaid
flowchart TD
    B1["Nate hears the 2077 recall broadcast in south Boston"] --> B2["Quest: report to division headquarters"]
    B2 --> B3["Meets the Devils' C-130 crew in the street"]
    B3 --> B4{"Is the Brotherhood at the airport?"}
    B4 -->|Yes| B5["The Devils trade technical manuals and avionics to keep flying"]
    B4 -->|"No, or gone"| B6["The crew works the airport undisturbed"]
    B5 --> J1{"Wearing power armor?"}
    B6 --> J1
    J1 -->|No| J2["Jumpmaster: 'You're not going out my door without a rig'"]
    J2 --> J1
    J1 -->|Yes| J3["The jump onto Sicily DZ, into a raider attack"]
    J3 --> J4["Fight beside Vargas's patrol. The Devils always win; the question is how well"]
    J4 --> V1{"How did the fight go?"}
    V1 -->|Heavy losses| V2["'Well, that was a clusterfuck...'"]
    V1 -->|In between| V3["'Could've been worse. Could've been a lot better. Start talking.'"]
    V1 -->|Overwhelming win| V4["'Nice shootin', Tex.'"]
    V2 --> V5["Vargas confirms the recall and the way: through the tunnels. Then the shakedown"]
    V3 --> V5
    V4 --> V5
    V5 --> V6{"'Hand over all your power cores.'"}
    V6 -->|"'Stick a power core up your ass!'"| H1["Fight. The Devils turn hostile; the tunnel unlocks. Siding with the Devils and the peace are gone"]:::hostile
    V6 -->|"'I'll have to think about it.'"| V7["Nothing happens; the tunnel stays locked"]
    V7 --> V6
    V6 -->|"'OK. Here they are.'"| V8["All cores but the one in the frame: 'See... I'm not a monster.' The tunnel unlocks"]
    V6 -->|No spare cores| V9["'Nothing? Hell, you're poorer than we are.' The tunnel unlocks"]
    V8 --> R1{"Later, on post: report Vargas?"}
    R1 -->|"Yes, to the hardliner"| R2["Vargas goes to the stockade. 'We don't have the location of your stolen items... yet.' Cores back near the end"]
    R1 -->|No| R3["Steal them back from the post, or let it go"]
    H1 --> T0["Into the tunnels (part 2)"]
    V8 --> T0
    V9 --> T0

    classDef hostile fill:#f8d7da,stroke:#b02a37,color:#000
```

## 2. The tunnels and the reactor

```mermaid
flowchart TD
    T0["The tunnels: three ways from the drop zone entrance"] --> T1{"Which way?"}
    T1 -->|East| E1["Raider camp and their guard gate"]
    E1 -.-> E2["The reactor and the storm drain to Bragg Blvd (idea: both past the raider gate)"]:::open
    T1 -->|North| N1["Bragg: the barracks area and division HQ. The reactor can wait; both orders have to work"]
    T1 -->|West| W1["Top's ghouls, at the edge of the hot zone and the radiation interlock"]
    W1 --> W2["Quest: restart the reactor to run the fans and vent the air"]
    W2 --> F1{"Fix the filters first?"}
    F1 -->|No| X1["Vent now: the air pours out over the barracks. Many Devils die; the Devils turn hostile for good"]:::hostile
    F1 -->|Yes| F2["Pull an old filter from a vent stack: a fight with the super mutants nesting there"]
    F2 --> F3{"Are the settlers hostile?"}
    F3 -->|No| F4["The settlers' hardliner: 'It'd be a shame if the filters got left out...' He makes the introduction anyway"]
    F4 --> F5["The tinker on Bragg Blvd makes 3 or 4 filters (parts list to decide)"]
    F3 -->|Yes| F6["The Devils' armorer makes them, at a price"]
    F5 --> F7{"Install the filters?"}
    F6 --> F7
    F7 -->|No| X1
    F7 -->|Yes| F8["Start the reactor. Nobody dies"]
    X1 --> P1["Reactor on: fans clear the hot zone, elevators run, defenses and the artillery wake, the post has power"]
    F8 --> P1
    P1 --> P2["Clear the ferals beside Top's squad: 'Put them down clean'"]
    P2 --> P3["Nate relieves Top and his squad. They become the first settlers of the player's settlement on post. Reward: Top's pearl-handled 1911"]
    P1 --> P4["The transmitter behind RonMike comes alive: a numbers station (part 3). Nate made RonMike speak: the Devils swing hard toward friendly"]
    P2 -.-> P5["Optional: the vault at the bottom, still hot. Does it still hold nukes?"]:::open

    classDef hostile fill:#f8d7da,stroke:#b02a37,color:#000
    classDef open fill:#fff,stroke:#888,stroke-dasharray:5 5,color:#000
```

## 3. The choice and the endings

```mermaid
flowchart TD
    Q1["Nate hears the numbers station: four-digit groups on a loop. The Devils think RonMike is speaking"] --> Q2["Quest: find out how to decode it"]
    Q2 --> Q3["Top: 'That's a numbers station. Useless without the book.'"]
    Q3 --> Q4["The trail leads to the settlers' codebook"]
    Q4 --> S1{"Pick a side"}
    Q4 --> L1["Optional: light up the Cue and Ale with the Food Lion's generator. The settlers swing hard toward friendly and give Nate the codebook"]
    L1 --> S1
    S1 -->|The Devils| D1["The Devils hand over the Key to the Post. The codebook is earned, stolen or taken. The settlers turn hostile"]:::hostile
    S1 -->|The settlers| S2["Take the Key to the Post from the Devils' commander, the worst insult there is. The Devils turn hostile"]:::hostile
    S1 -->|"Peace (speech checks)"| PC["The reform officer and the moderate settler leader bring both halves to the door together. Bringing the conscript home the right way unlocks the volunteers check"]
    D1 --> FM{"The Devils' hardliner: authorize a fire mission on the Cue and Ale market?"}
    FM -->|Yes| FM1["The market is shelled. Many settlers die; the settlers are hostile for good"]:::hostile
    FM -->|No| A0
    FM1 --> A0
    S2 --> A0
    PC --> A0
    A0["The armory door: Nate's ID + the Key to the Post + the code from the broadcast + the codebook to find it. Every ending: the armory's gear and the Airborne perk"] --> A1{"What does Nate do?"}
    A1 -->|"Open it (Devils' path)"| END1["The settlers are safe from raids and live under the Devils for good. Hardliner or reformer decides how that feels. Reward: artillery on call"]
    A1 -->|"Open it (settlers' path)"| END2["The settlers are free, and the raids get worse. Can they hold? Reward: the market opens up, and a unique armor"]
    A1 -->|"Open it (peace)"| END3["The raids continue, but the two sides face them together. Reward: the C-130 between Boston and Bragg, on demand"]
    A1 -->|Destroy it| END4["Nobody gets it. Both sides turn hostile; Nate is on his own. Reward: loot it all first (a backpack nuke, if the vault has them)"]:::hostile
    A1 -.-> NK["What's inside, and do nukes come with it?"]:::open

    classDef hostile fill:#f8d7da,stroke:#b02a37,color:#000
    classDef open fill:#fff,stroke:#888,stroke-dasharray:5 5,color:#000
```

## Still undecided

- What's in the armory, and whether the vault still holds nukes.
- Where the reactor and the storm drain sit (leaning: east, past the raider gate).
- What the tinker needs for the filters.
