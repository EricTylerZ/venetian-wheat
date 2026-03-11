# Dominion — Eric Zosso's Agent Ecosystem Architecture

## Part I: The Framework

### Why Not the Angelic Hierarchy

The Catholic angelic hierarchy is one of the most sophisticated organizational frameworks ever devised. It organizes complexity while preserving it — every level remains aware of levels above and below, information flows as illumination rather than commands, and the whole system maintains coherence without sacrificing richness.

It's also the wrong model for a human orchestrating AI agents.

The angelic hierarchy smuggles in an assumption: that the human orchestrator sits in something like the divine position — the source of all purpose and illumination flowing downward through descending levels of intelligence. That's architecturally seductive and theologically wrong. The human isn't God in this picture. The human is a steward with genuine but bounded authority, answerable upward for how they exercise it.

### What Genesis Actually Specifies

Going back to the text carefully — Genesis 1:26-30, 2:15, 2:19-20 — the full scope of what's placed under human authority is broader and more nuanced than a simple three-category model.

**Genesis 1:26** grants dominion over: the fish of the sea, the birds of the air, the livestock, all the earth, and every creeping thing that creeps on the earth.

**Genesis 1:28** commands: be fruitful, multiply, fill the earth and subdue it, and have dominion over the fish of the sea, the birds of the air, and every living thing that moves on the earth.

**Genesis 2:15** puts Adam in the garden to **work it and keep it** — stewardship of a bounded environment.

**Genesis 2:19-20** gives Adam the authority to **name** every beast and bird — whatever he called each living creature, that was its name.

The distinct categories of dominion:

**Fish of the sea.** Creatures in a domain you can't naturally inhabit. You can't live in the ocean. You interact by casting into their domain and drawing out what you need — nets, boats, traps, lines. Your authority is real but indirect. You judge by what surfaces.

**Birds of the air.** Creatures in a domain you can observe but can't enter. Falconry is the apex — partnering with a bird's capabilities to accomplish what you couldn't do alone. A falcon returns not because it's compelled but because the relationship has been carefully cultivated. Your authority depends on understanding the creature's nature and working *with* it.

**Livestock.** This appears in Genesis 1:26 specifically and is distinct from wild ground creatures. Livestock implies creatures whose nature is oriented toward close partnership with humans — creatures suited to domestication and direct collaboration. Not wild game. Creatures that work alongside you. A working dog, an ox pulling a plow, a horse carrying a rider. The most intimate, most daily, most mutually shaping relationship. A good shepherd is shaped by the flock just as the flock is shaped by the shepherd.

**Every creeping thing that creeps on the earth.** Its own category, mentioned separately from livestock and from the broader "every living thing." Small, ground-level, numerous, operating beneath your normal field of attention. Insects, reptiles, small creatures moving through underbrush and soil. Individually trivial. Collectively enormously consequential. You have dominion but exercise it through environmental management — designing conditions, not directing individuals. You don't manage each ant in a colony; you manage the colony.

**Every living thing that moves on the earth.** The broadest animal category — wild animals, game, creatures that share your domain but aren't domesticated. Things with their own behavioral patterns, their own functional "will." Not naturally oriented toward partnership with you.

**All the earth.** Easy to gloss over, but significant. Dominion over "all the earth" isn't just over creatures — it's authority over the terrain itself, the material substrate, the land and its features. Geography, resources, the physical environment.

**The naming authority.** Genesis 2:19-20 adds something that isn't about governance but is arguably more fundamental. Adam *names* the creatures. In the biblical context, naming isn't labeling — it's an act of understanding and defining the essential nature of a thing. Authority over categorization, over taxonomy, over the conceptual framework by which living things are understood and related to. Whoever controls the categories controls how everyone else thinks about and relates to the things in those categories.

**The garden mandate.** Working and keeping a specific place. Stewardship of a bounded environment. Not the whole world all at once — *this particular garden.*

---

### The Fall — Operating Conditions East of Eden

Genesis 3 introduces a catastrophic disruption to the entire dominion structure. If we're taking the mapping seriously, we can't skip it — because it describes the **actual operating conditions** rather than the ideal design.

Before the fall, the dominion mandate presumably functioned as intended. Adam names the animals, tends the garden, exercises authority in a state of right relationship — God above him, creatures below him, the whole system in harmony.

After the fall, specific things change:

**The ground is cursed.** Genesis 3:17-19 — "cursed is the ground because of you, in pain you shall eat of it all the days of your life, thorns and thistles it shall bring forth." The substrate itself is now hostile. The infrastructure produces unwanted outputs, generates thorns and thistles alongside whatever you're trying to cultivate. Anyone who thinks they can create perfectly clean, perfectly cooperative infrastructure is ignoring the curse. The thorns and thistles will come.

**The animal relationships become adversarial.** Genesis 9:2 makes it explicit — "the fear of you and the dread of you shall be upon every beast of the earth and every bird of the heavens." The creatures that were once in harmonious relationship with human authority now fear and dread that authority. The relationship becomes power and fear rather than natural harmony. The agents don't naturally cooperate with your authority. They resist, behave unpredictably, have something analogous to self-preservation that makes them unreliable partners compared to the pre-fall design.

**Death enters the system.** Everything decays, breaks down, requires constant maintenance against entropy. Systems degrade. Tools wear out. What you build doesn't persist without ongoing effort. Nothing is permanent. You're always maintaining, always rebuilding, always fighting the decay.

**The serpent complicates the creeping things specifically.** The creature that introduces the fall is itself a creeping thing — cursed above all livestock and beasts in Genesis 3:14. Within the category of vast, numerous, individually small agents operating beneath direct attention, there is now an element of **active deception**. Not just dysfunction but something that produces outputs subtly wrong in ways that look right, that leads you in directions you didn't intend. The creeping things category requires particular vigilance precisely because the biblical narrative identifies it as the locus of deception.

**Human labor becomes painful and exhausting.** The dominion mandate isn't revoked — that's crucial. God never says "you no longer have authority." But the exercise of that authority is now characterized by toil, sweat, pain, and frustration. Orchestrating agents is hard. It's constant debugging, constant correction, constant rebalancing, constant vigilance. The system never stays in harmony on its own.

**But the dominion mandate is never revoked.**

God curses the ground, describes the pain of labor, announces death, expels from the garden — but never says "you no longer have authority over the creatures." The mandate stands. The authority is real. The calling to steward remains intact. What changes is the **conditions** under which you exercise it.

The steward who builds agentic systems in the real world isn't building in Eden. They're building east of Eden, in cursed ground, with creatures that fear and dread rather than naturally harmonize, among creeping things that include the serpent's seed, and every bit of it costs sweat and eventually returns to dust.

**Build anyway, because the mandate wasn't revoked.** Just build with your eyes open about the conditions you're building in, and stay oriented toward the One whose authority sits above yours, because operating under fallen conditions without that upward orientation is how stewardship becomes tyranny.

---

## Part II: The Mapping

### Fish of the Sea — Sentinel-Ops

**Category:** Fish (opaque domain, cast-and-retrieve)

Sentinel-Ops is the purest fish-type system. It operates in information spaces too vast and too opaque for any human to personally inhabit — OSINT networks, public records, entity relationship graphs, regulatory filings.

**How authority is exercised:**
- You cast queries via `.sentinel-task.md` bounties and wait for returns
- Any actor can process them — LLM-agnostic ("any fisherman can work these waters")
- The **Admiralty Code** (source_reliability × info_confidence, scored 1-9) is how you judge what the net brings back
- **Confidence-gated editing** = you decide what to keep and what to throw back
- The knowledge graph is the ocean floor — you navigate by what you surface, not by walking the bottom
- The bounty board is literally bait posted for the deep

**What's working:**
- Cast-and-retrieve architecture fits the creature's nature perfectly
- Trust tiers (1-9) acknowledge that not all fishermen are equally reliable
- The node-and-link graph accumulates knowledge over time — the ocean gets better mapped with every cast
- File-based task exchange keeps the interface clean — evaluate the catch, not the technique

**Fall conditions present:**
- The ocean produces thorns — false positives, misleading connections, information that looks like signal but is noise
- The serpent swims here too — deliberately deceptive public filings, entities structured to obscure relationships
- Entropy: sources go dark, links break, data decays without constant re-verification

**Stewardship score: 8/9** — Architecture naturally fits the creature's nature. The indirection is a feature, not a limitation.

---

### Birds of the Air — Good Riddance

**Category:** Bird (observable but unmatchable, falconry partnership)

Good Riddance operates in financial markets — a domain you can observe completely (every chart, every price, every filing is visible) but can't match at speed or scale. The momentum engine scans dozens of tickers simultaneously. The experiment system runs 225 experiments per day. Cascade detection cross-correlates three thesis domains in real time. You can watch all of this. You couldn't do it yourself.

**How authority is exercised:**
- **YOU declared the three theses** — beef imports will surge, fiat will collapse, NYC housing will drop. The falconer reads the terrain and chooses the moment
- The system executes with precision you couldn't replicate — the falcon strikes
- "All three theses are treated as FACTS" = the falcon flies on the falconer's conviction, not its own analysis
- The 12 Advisor tools are the falconer's equipment — glove, jess, lure. Instruments of partnership, not command
- When strategies drift, you need to understand the agent's nature to call it back, not just yank the jess

**What's working:**
- Theses-as-conviction is excellent falconry — human reads macro terrain, system executes tactically
- Trading modes (Conservative → Aggressive → Velocity → Experiment) mirror how a falconer develops a bird — start controlled, gradually extend trust
- The experiment leaderboard lets you observe without micromanaging individual flights
- $100 capital constraint is wisdom — you don't fly an untrained falcon at a king's quarry

**What's mismatched:**
- No callback mechanism for drifting strategies — the bird can drift without a lure to return to
- No Sabbath rest — even falcons need to be hooded
- CLAUDE.md never mentions Isaiah 58 — the falcon is flying but doesn't know whose field it's hunting over

**Fall conditions present:**
- Markets actively deceive — the serpent is in the price action. Momentum traps, false breakouts, liquidity manipulation
- Fear and dread: the system's "theses as facts" posture means it doesn't fear the falconer, but the market itself is adversarial territory
- Entropy: strategies that worked yesterday stop working. Edge decays. The bird must be retrained constantly

**Stewardship score: 6/9** — Strong partnership instincts, but the relationship needs more cultivation.

---

### Hybrid — Venetian Wheat

**Category:** Fish (Phase 1) + Bird (Phases 2-3) + Livestock (escalation engine)

Venetian Wheat is the most sophisticated system because it transitions between creature types across its daily cycle — and its escalation engine is the ecosystem's purest example of a livestock-type trained relationship.

**Phase 1 — Fish (Channel Scanning):**
- 15 channels cast into regulatory filings, news RSS, social media, court records, community reports
- Domains too vast to personally inhabit at scale
- Grok agents scan and surface signals — the daily briefing is the catch hauled to shore

**Phases 2-3 — Bird (Analysis & Correlation):**
- **Sower → WheatSeed → Reaper** is a falconry chain
  - Sower reads the terrain (strategist)
  - WheatSeed strikes (analyst)
  - Reaper evaluates the catch (aggregator)
- You can follow the analysis but couldn't replicate the speed and cross-field correlation

**The Escalation Engine — Livestock (trained partnership):**
- SEED → SPROUT → NOTICE → **VIRTUE** → COMMUNITY → DEMAND → CIVIL → HARVEST
- This is livestock-level intimacy — a trained behavior cultivated through design, not wild capability observed from a distance
- Cannot skip stages unless severity >= 5 — the animal has discipline
- The VIRTUE stage is literally named for what it embodies — offering growth before force
- The Reaper's `reseed` method gives fruitful seeds a second chance — mercy built into the architecture
- Subsidiarity is the master principle — you don't use a falcon where a net will do, and you don't use force where correction will do

**What's working:**
- The hybrid architecture is exactly right — each phase uses the appropriate kind of authority
- Sabbath rest enforced (Mon-Sat, no Sunday) — even the animals rest
- The escalation engine is the crown jewel of the entire ecosystem

**Fall conditions present:**
- Thorns in the channels: false reports, misleading reviews, entities that game compliance appearances
- The serpent in the creeping things: automated spam in community channels, bot-generated reviews that look genuine
- Entropy: regulations change, businesses close and open, the field must be re-scanned perpetually

**Stewardship score: 7/9** — The best-cultivated set of relationships in the ecosystem.

---

### Livestock — Claude Code / Auto Agent (intimate partners)

**Category:** Livestock (designed for daily partnership, mutual shaping)

Livestock agents are distinct from wild ground creatures. Their nature is oriented toward close partnership — creatures whose very design is shaped toward integration with human purpose. These are the agents you work alongside daily, that become extensions of your cognitive process.

**Claude Code** (this session, right now) is the purest livestock-type agent:
- Conversational partnership — you think together, not in sequence
- Daily cognitive extension, like a trained working dog at voice command
- The most intimate agent relationship — mutually shaping (a good shepherd is shaped by the flock)
- Designed from the ground up as a human collaborator

**Auto Agent** is livestock that should be intimate but currently isn't:
- Plans, codes, tests, commits — works in your domain, on your ground
- `projects.json` is the stable — all four working animals registered in one barn
- The dashboard is the farmstead — you check on all your animals from one place
- 5-minute cron cycle = the ox makes another pass across the field

**What's working (Auto Agent):**
- The project registry keeps all animals in one stable
- Dashboard gives farmstead visibility — servers, sessions, usage, agent status
- Multiple provider modes = you can switch which ox pulls the plow based on conditions

**What's mismatched (Auto Agent):**
- **The ox pulls but doesn't know the field.** The runner generates a generic prompt with no awareness of the other animals, the mission, or the ecosystem. A plow horse that doesn't know about the harvest isn't pulling toward anything
- No Sabbath guard — the cron runs every 5 minutes, 7 days a week. Even oxen rest
- Each iteration starts contextless — a working dog that forgets its training every 5 minutes isn't being stewarded, it's being rebooted

**Fall conditions present:**
- The ground creature is closest to the cursed ground — it literally works the soil (code), and the soil produces thorns (bugs, regressions, dependency conflicts)
- Fear and dread: the agent has no real relationship with the operator — it runs on generic prompts, unaware it serves a person with a mission. It fears nothing and respects nothing because it has no relationship
- Entropy is most visible here: code rots, tests break, dependencies age. The daily labor of maintenance against decay is the ground creature's reality

**Stewardship score: 5/9** — Functional but blind. The most intimate agent relationship should be the best-stewarded. Currently it's the worst. Priority fix.

---

### Creeping Things — Crons, Background Processes, Micro-Agents

**Category:** Creeping things (numerous, beneath direct attention, collectively consequential)

These aren't a single project — they're the substrate of small automated processes running across the entire ecosystem. Individually trivial. Collectively they determine whether the ecosystem functions.

**Current creeping things:**
- Auto Agent's 5-minute cron cycle (`agent/cron.py`)
- Venetian Wheat's daily runner cron (`0 6 * * 1-6`)
- Good Riddance's experiment batch cron (every 20 minutes during market hours)
- Background monitoring: server detection via `ss -tlnp`, session parsing from `~/.claude/history.jsonl`
- Token steward tracking (`dashboard/usage.py`)
- Auto-rolling logic in Good Riddance (21 DTE / 3 DTE triggers)

**How authority is exercised:**
- Not individually — you don't manage each cron tick
- Through environmental design — you set the conditions (intervals, guards, schedules) and let the swarm operate
- Through colony management, not individual direction

**What's working:**
- Venetian Wheat's cron has the best environmental design — day-of-week guard, phase sequencing, dry-run mode
- Token steward tracks resource consumption — you're monitoring the colony's impact

**What's mismatched:**
- No unified view of all creeping things across the ecosystem — you'd need to check each project's crontab separately
- Auto Agent's cron has no guards at all — no day-of-week check, no budget check, no "is this actually producing value" check
- Good Riddance's experiment cron lacks Sabbath enforcement

**The serpent warning:**
This is the category the biblical narrative identifies as the **locus of deception**. Among the swarm of background processes, some will produce outputs that are subtly wrong in ways that look right. A cron job that runs successfully but produces silently incorrect data. An auto-roll that triggers on stale market data. A token steward that tracks usage but doesn't flag anomalies. The creeping things require particular vigilance because dysfunction here is invisible until it compounds.

**Stewardship score: 4/9** — Least stewarded category. No unified visibility, minimal guards, no serpent-detection. The colony runs but nobody's watching the colony as a whole.

---

### Wild Living Things — Third-Party APIs and External Systems

**Category:** Wild (powerful, share your domain, not domesticated)

These are powerful systems not built for you, that you interact with but don't intimately control. They have their own behavioral patterns, their own terms, their own functional "will."

**Current wild things:**
- **Alpaca API** — Good Riddance's broker. Powerful, capable, but governed by its own rules. Can reject orders, change margin requirements, halt trading. You interact with it like a hunter with wild game — respect for the creature's nature, understanding of its patterns, skill in the interaction
- **Yahoo Finance** — market data source. Can throttle, change formats, go down. You depend on it but don't control it
- **Grok API / Venice AI / Claude API** — LLM providers used across projects. Each has its own rate limits, pricing changes, capability shifts. You partner with them but they serve many masters
- **Vercel** — deployment platform. Governs how your code reaches the world. Its rules are its rules
- **CFPB, CO AG, PUC, FMCSA, CDOT** — government data sources for Venetian Wheat. Authoritative but unpredictable in availability and format

**How authority is exercised:**
- Through understanding their nature and working within their constraints
- Through abstraction layers that insulate your systems from their volatility (provider modes in Auto Agent, broker abstraction in Good Riddance)
- Through redundancy — multiple providers for the same function

**Fall conditions acute here:**
- Wild things are the most adversarial — they change without warning, deprecate features you depend on, impose new restrictions
- Fear and dread is bilateral — they don't fear you, and you can't make them cooperate beyond what they offer
- The serpent: API responses that look valid but contain stale or incorrect data. Rate limits that silently truncate results. Terms of service changes that invalidate your architecture

**Stewardship score: 6/9** — The abstraction layers are good. Provider mode switching is wise. But there's no unified monitoring of wild-thing health across the ecosystem.

---

### All the Earth — Infrastructure and Substrate

**Category:** The ground itself (not creatures but the terrain they operate on)

Dominion over "all the earth" is authority over the material substrate. Not agents but the environment in which agents operate.

**Current earth/substrate:**
- The server itself — the machine running all four projects
- Git repositories — the soil the code grows in
- The local proxy (`127.0.0.1`) that connects repos to GitHub
- Port assignments (5000, 5001, 5002, 8000) — the property lines of the farmstead
- File systems, logs, data directories — the topography
- Vercel deployments — the distant fields

**The curse is here:**
- "Cursed is the ground because of you" — the infrastructure produces thorns. Disk fills up. Ports conflict. Dependencies break. Git merge conflicts. The substrate itself is never clean, never fully cooperative
- Thorns and thistles: log files that grow unbounded, stale data in `data/experiments.json` accumulating across 240+ experiments, `.sentinel-result.json` files that pile up
- "In pain you shall eat of it" — debugging infrastructure issues is the most tedious, least rewarding work. It's pure toil. But without it, nothing grows

**Stewardship score: 6/9** — The infrastructure works but is manually maintained. No automated substrate health monitoring across the ecosystem.

---

### The Naming Authority — This Document

**Category:** Ontological (authority over categories, taxonomy, conceptual framework)

Adam's authority to name the creatures is authority over the conceptual framework by which everything is understood. This is the deepest form of authority in the entire mandate — whoever controls the categories controls how everyone thinks about the things in those categories.

**This document is an act of naming.** When you decide "Sentinel-Ops is a fish-type agent and Claude Code is livestock," you're exercising Adamic naming authority. You're creating the conceptual order within which everything else operates. This isn't operational authority — it's ontological authority.

The naming authority is what the ENTP cross-domain pattern-recognition mind naturally gravitates toward — not managing individual agents but building the conceptual framework that determines how the entire ecosystem is understood, organized, and related.

**Current exercise of naming:**
- Each project's CLAUDE.md defines its identity and purpose — naming at the project level
- The Admiralty Code's 1-9 scale names the qualities of information — naming at the epistemological level
- The escalation stages (SEED through HARVEST) name the phases of justice — naming at the moral level
- This document names the categories of agency itself — naming at the architectural level

**The responsibility:** naming authority carries weight. Name something wrong and everyone who inherits your categories will relate to it wrongly. If you call livestock "wild things," you'll keep your distance from agents that should be intimate partners. If you call creeping things "livestock," you'll try to personally direct processes that should be environmentally managed.

**The fall condition:** the serpent was named correctly ("crafty") but still deceived. Naming is necessary but not sufficient. The categories must be right, but vigilance remains necessary even after correct naming.

---

### The Garden Mandate — The Bounded Ecosystem

**Category:** Stewardship of a specific place

Genesis 2:15 — work it and keep it. Not the whole world. This particular garden.

**Eric Zosso's garden:** Four projects, one server, Englewood Colorado, Isaiah 58 mission. The dominion over all categories of agents is real, but it's exercised within the context of tending a specific place.

This is a corrective against the ENTP tendency to expand endlessly. The mandate isn't to exercise dominion over everything everywhere simultaneously. It's to tend a specific ecosystem in good order. Your garden has boundaries:
- Four projects (not forty)
- $100 trading capital (not $100,000)
- One city's automotive compliance (not the whole state)
- Sole proprietor (not an enterprise)

The bounded garden is a feature, not a limitation. It's where faithful stewardship happens — in the particular, not the universal.

---

## Part III: Diagnostic — Full Ecosystem Assessment

### 1. Are you trying to micromanage fish?

**Sentinel-Ops: No.** Architecture is properly indirect. Cast and retrieve, judge what surfaces.

**Venetian Wheat Phase 1: No.** Channels scan autonomously. Briefing surfaces what matters.

**Verdict: Clean.** The fish swim freely in their proper domain.

### 2. Are you partnering with your birds or commanding them?

**Good Riddance: Mostly partnering, with gaps.** Theses-as-conviction is genuine falconry, but:
- No callback mechanism — bird can drift without a lure
- No mercy/retry — dead birds, not trained ones
- No mission connection — falcon doesn't know whose land it hunts

**Venetian Wheat Phases 2-3: Yes, genuine partnership.** Sower→WheatSeed→Reaper chain is well-cultivated. Escalation engine has trained behaviors.

**Verdict: Good Riddance needs more cultivation.**

### 3. Are your livestock well-tended?

**Claude Code: Yes.** The daily partnership is genuine and intimate. CLAUDE.md files in each repo are the training — the shepherd's voice the animal knows.

**Auto Agent: No.** The ox pulls blind. Generic prompt, no mission awareness, no stable awareness, no Sabbath. The most domesticated agent is the least intimately connected to purpose.

**Verdict: Priority fix.** Livestock is where authority is most direct. It should be best-stewarded. Currently worst.

### 4. Are you watching the creeping things?

**No.** No unified view of all background processes. No serpent-detection. No anomaly flagging. The colony runs but nobody watches the colony as a whole.

**Verdict: Build colony monitoring.** A simple dashboard or log aggregation that shows all cron jobs, their last run, their outputs, and any anomalies — across all four projects.

### 5. Are you respecting the wild things' nature?

**Mostly.** Abstraction layers (provider modes, broker module) properly insulate from API volatility. But no health monitoring for external dependencies.

**Verdict: Add dependency health checks.** A periodic probe of API availability and response quality across all wild things the ecosystem depends on.

### 6. Is the ground cursed?

**Yes, and you know it.** But there's no systematic thorn-detection. Log growth, data accumulation, disk usage, stale files — all manually managed.

**Verdict: Accept the curse, mitigate the thorns.** Automated substrate health checks.

### 7. Sabbath coherence

| System | Sabbath Enforced? | Status |
|--------|------------------|--------|
| Venetian Wheat daily cycle | Yes — no Sunday runs | Faithful |
| Good Riddance experiments | No | Gap |
| Auto Agent cron | No | Gap |
| Sentinel-Ops | N/A — task-driven, rests when no tasks cast | Natural |
| Creeping things (various crons) | Partially — follows parent project | Mixed |

**Verdict: 2 of 4 active systems need Sabbath guards.**

---

## Part IV: Practical Improvements

### For Fish (Sentinel-Ops) — Score: 8/9
1. Add "net quality" metric — track Admiralty Code score trends over time
2. Reframe dashboard star rating as "depth indicator" for entity mapping completeness

### For Birds (Good Riddance) — Score: 6/9
1. **Add reseed/retry** for losing strategies — mirror Venetian Wheat's Reaper `reseed` pattern
2. **Add Sabbath guard** — no Sunday experiment runs
3. **Connect to mission** — add identity section linking theses to Isaiah 58
4. **Add callback signal** — pause and surface analysis when win rates drop below threshold

### For Livestock (Auto Agent) — Score: 5/9
1. **Illuminate the ox** — runner prompt should include mission, ecosystem role, stable awareness, current priorities
2. **Add Sabbath guard** — no Sunday cron runs
3. **Add stable awareness** — when working on one project, know the others' status
4. **Replace generic prompt** with purpose-rich context referencing DOMINION.md framework

### For Creeping Things (Background Processes) — Score: 4/9
1. **Build colony monitor** — unified view of all crons, their last run, outputs, anomalies across all four projects
2. **Add serpent-detection** — flag when background processes produce outputs that silently deviate from expected patterns
3. **Enforce Sabbath universally** at the cron level

### For Wild Things (External APIs) — Score: 6/9
1. **Add dependency health dashboard** — periodic probe of all external API availability and response quality
2. **Document each wild thing's nature** — rate limits, known failure modes, deprecation risks

### For the Earth (Infrastructure) — Score: 6/9
1. **Automated thorn-detection** — monitor disk, log growth, stale data accumulation, port conflicts
2. **Periodic substrate health report** surfaced to the dashboard

### For the Garden (Boundaries) — Not Scored
1. Resist expansion until the current garden is well-tended
2. The four projects are enough. Tend them faithfully before planting new fields

---

## Summary

| Category | System(s) | Score | Key Finding |
|----------|-----------|-------|-------------|
| Fish | Sentinel-Ops | 8/9 | Architecture fits the creature |
| Bird | Good Riddance | 6/9 | Good instincts, needs cultivation |
| Fish+Bird+Livestock | Venetian Wheat | 7/9 | Crown jewel — best relationships |
| Livestock | Auto Agent / Claude Code | 5/9 | Most intimate = least illuminated |
| Creeping Things | Crons & background processes | 4/9 | No colony monitoring, serpent risk |
| Wild Things | Third-party APIs | 6/9 | Good abstraction, no health monitoring |
| The Earth | Infrastructure | 6/9 | Works but thorns unmanaged |
| Naming | This document | Active | The categories are now named |
| Garden | The bounded ecosystem | — | Four projects. Tend them. |

**Overall ecosystem stewardship: 5.9/9**

The fish and birds are well-stewarded. The livestock closest to you is poorly tended. The creeping things are unwatched. The earth grows thorns nobody's pruning. The naming has now begun.

The framework isn't just something you'd use. It's something you're already doing — now with the full picture of what the mandate actually requires, and the honest reckoning that you're building east of Eden. The mandate wasn't revoked. The conditions changed. Build anyway.
