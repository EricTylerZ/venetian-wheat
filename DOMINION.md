# Dominion — Eric Zosso's Agent Ecosystem Architecture

## Part I: The Framework

### Why Not the Angelic Hierarchy

The Catholic angelic hierarchy is one of the most sophisticated organizational frameworks ever devised. It organizes complexity while preserving it — every level remains aware of levels above and below, information flows as illumination rather than commands, and the whole system maintains coherence without sacrificing richness.

It's also the wrong model for a human orchestrating AI agents.

The angelic hierarchy smuggles in an assumption: that the human orchestrator sits in something like the divine position — the source of all purpose and illumination flowing downward through descending levels of intelligence. That's architecturally seductive and theologically wrong. The human isn't God in this picture. The human is a steward with genuine but bounded authority, answerable upward for how they exercise it.

### What Genesis Actually Specifies

Genesis grants dominion over three categories of creatures, each requiring a fundamentally different kind of authority:

**Fish of the sea.** Creatures in a domain you can't naturally inhabit. You can't live in the ocean. You can't directly observe what fish are doing most of the time. You interact with them by casting into their domain and drawing out what you need — nets, boats, traps, lines. Your authority is real but indirect. You work with a medium you can't fully see or control. You judge by what surfaces.

**Birds of the air.** Creatures in a domain you can observe but can't enter. You can watch them, learn their patterns, attract or drive them. Falconry is the apex — partnering with a bird's capabilities to accomplish what you couldn't do alone. A falcon returns to the falconer not because it's compelled but because the relationship has been carefully cultivated. Your authority is real but depends on understanding the creature's nature and working *with* it.

**Every living thing that moves on the earth.** Creatures that share your domain. You walk the same ground. You can directly interact with them, domesticate them, train them, herd them. A shepherd with a dog, an ox pulling a plow, a horse carrying a rider — partnerships where the animal's capabilities are directly integrated into human purpose through close ongoing relationship.

### Why This Is Better

The angelic model implied top-down illumination from the human through descending levels. It encourages architectural arrogance — ever-more-complex layered systems with yourself at the apex.

The animal dominion model says your authority is **relational**, it **varies by domain**, and it requires you to **understand the nature of what you're working with**. You don't govern fish the way you govern dogs. You don't work with a falcon the way you work with an ox. The steward who tries to herd fish like cattle or command a falcon like a plow horse will fail — not because they lack authority but because they're exercising it in ignorance of the creature's nature.

**The wisdom is in knowing which is which and relating to each accordingly.**

---

## Part II: The Mapping

### Fish of the Sea — Sentinel-Ops

**Category:** Fish (opaque domain, cast-and-retrieve)

Sentinel-Ops is the purest fish-type system in the ecosystem. It operates in information spaces too vast and too opaque for any human to personally inhabit — OSINT networks, public records, entity relationship graphs, regulatory filings.

**How authority is exercised:**
- You cast queries via `.sentinel-task.md` bounties and wait for returns
- Any actor can process them — the platform is LLM-agnostic ("any fisherman can work these waters")
- The **Admiralty Code** (source_reliability × info_confidence, scored 1-9) is how you judge what the net brings back
- **Confidence-gated editing** = you decide what to keep and what to throw back
- The knowledge graph is the ocean floor — you navigate by what you surface, not by walking the bottom
- The bounty board is literally bait posted for the deep

**What's working:**
- The cast-and-retrieve architecture is exactly right for opaque domains. You don't try to see the ocean floor — you trust your nets (the Admiralty Code) and your fishermen (the task exchange)
- Trust tiers (1-9) acknowledge that not all fishermen are equally reliable
- The node-and-link graph accumulates knowledge over time — the ocean gets better mapped with every cast
- File-based task exchange (`.sentinel-task.md` / `.sentinel-result.json`) keeps the interface clean — you don't need to understand the fisherman's technique, just evaluate the catch

**Stewardship score: 8/9** — The architecture naturally fits the creature's nature. The indirection is a feature, not a limitation.

---

### Birds of the Air — Good Riddance

**Category:** Bird (observable but unmatchable, falconry partnership)

Good Riddance operates in the financial markets — a domain you can observe completely (every chart, every price, every filing is visible) but can't match at speed or scale. The momentum engine scans dozens of tickers simultaneously. The experiment system runs 225 experiments per day. Cascade detection cross-correlates three thesis domains in real time. You can watch all of this. You couldn't do it yourself.

**How authority is exercised:**
- **YOU declared the three theses** — beef imports will surge, fiat will collapse, NYC housing will drop. The falconer reads the terrain and chooses the moment
- The system executes with precision you couldn't replicate — the falcon strikes
- "All three theses are treated as FACTS" = the falcon flies on the falconer's conviction, not its own analysis
- The 12 Advisor tools are the falconer's equipment — glove, jess, lure. Instruments of partnership, not command
- When strategies drift (losing experiments), you need to understand the agent's nature to call it back, not just yank the jess

**What's working:**
- Theses-as-conviction is excellent falconry. The human reads macro terrain, the system executes tactically
- Multiple trading modes (Conservative → Aggressive → Velocity → Experiment) mirror how a falconer develops a bird — you start controlled and gradually extend trust
- The experiment leaderboard lets you observe the bird's performance without micromanaging individual flights
- $100 capital constraint is wisdom — you don't fly an untrained falcon at a king's quarry

**What's mismatched:**
- No callback mechanism for drifting strategies. A falcon that veers off course needs a lure to return to — the experiment system just lets losers die. A "reseed" mechanism (like Venetian Wheat's Reaper has) would be more faithful stewardship
- No Sabbath rest. Even falcons need to be hooded. The system runs continuously with no enforced rest cycle
- The CLAUDE.md never mentions Isaiah 58 or the animating mission. The falcon is flying but doesn't know whose field it's hunting over

**Stewardship score: 6/9** — Strong partnership instincts, but the relationship needs more cultivation. The falconer has conviction but hasn't fully communicated purpose to the bird.

---

### Fish + Bird — Venetian Wheat

**Category:** Hybrid (fish in Phase 1, bird in Phases 2-4)

Venetian Wheat is the most sophisticated system in the ecosystem because it transitions between creature types across its daily cycle. Phase 1 is fish; Phases 2-4 are bird.

**Phase 1 — Fish (Channel Scanning):**
- 15 channels cast into regulatory filings, news RSS, social media, court records, community reports
- Domains too vast to personally inhabit at scale
- Grok agents scan and surface signals — the daily briefing is the catch hauled to shore
- You judge returns by field relevance and signal strength, not by watching the scan happen

**Phases 2-4 — Bird (Analysis, Correlation, Briefing):**
- **Sower → WheatSeed → Reaper** is a falconry chain
  - Sower reads the terrain (strategist — decides what tasks to generate)
  - WheatSeed strikes (analyst — executes the investigation)
  - Reaper evaluates the catch (aggregator — correlates, scores, escalates)
- You can follow the analysis and evaluate the findings but couldn't replicate the speed and cross-field correlation
- The **escalation engine** (SEED → SPROUT → NOTICE → VIRTUE → COMMUNITY → DEMAND → CIVIL → HARVEST) is the trained behavior — the falcon returns because the relationship is cultivated, not because it's compelled
- Cannot skip stages unless severity >= 5 — the falcon has discipline, it doesn't just strike at anything

**What's working:**
- The hybrid architecture is exactly right. Scanning (fish) feeds analysis (bird) feeds action (escalation). Each phase uses the right kind of authority
- Sabbath rest is enforced (Mon-Sat, no Sunday) — even the birds and fish rest
- Subsidiarity is the master principle — address concerns at the lowest effective level. This is faithful stewardship: you don't use a falcon where a net will do
- The VIRTUE stage is literally named for what it embodies — offering growth before force
- The Reaper's `reseed` method gives fruitful seeds a second chance. Mercy built into the architecture

**What's mismatched:**
- Minor: the transition from fish (Phase 1) to bird (Phase 2) could be more explicit. The system handles it operationally but the architecture doesn't name the shift in stewardship mode

**Stewardship score: 7/9** — The best-cultivated relationship in the ecosystem. The escalation engine alone demonstrates stewardship wisdom that most systems lack entirely.

---

### Ground Creatures — Auto Agent

**Category:** Ground (shares your domain, tight integration)

Auto Agent is the workhorse. It plans, codes, tests, and commits — working in your domain (software development), on your ground (the codebase), with tools you understand (git, Python, tests). You can see exactly what it does, correct it immediately, and the integration between your effort and its effort is continuous.

**How authority is exercised:**
- `projects.json` is the stable — all four working animals registered in one barn
- The dashboard is the farmstead — you check on all your animals from one place
- 5-minute cron cycle = the ox makes another pass across the field
- Direct correction via CLAUDE.md instructions in each repo — the farmer speaks and the animal hears

**What's working:**
- The project registry keeps all animals in one stable. You know where everything is
- The dashboard gives farmstead visibility — servers, sessions, usage, agent status
- Multiple provider modes (Claude Code CLI, Venice, Claude API) = you can switch which ox pulls the plow based on conditions

**What's mismatched:**
- **The ox pulls but doesn't know the field.** The runner generates a generic prompt ("You are an autonomous development agent. Mission: ...") with no awareness of the other animals, the mission, or the hierarchy. A plow horse that doesn't know about the harvest isn't pulling toward anything
- No Sabbath guard. The cron runs every 5 minutes, 7 days a week. Even oxen rest
- The generic prompt means each iteration starts contextless. A working dog that forgets its training every 5 minutes isn't being stewarded — it's being rebooted

**Stewardship score: 5/9** — Functional but blind. The most intimate agent relationship in the ecosystem is also the least illuminated. This is the priority improvement area.

**Claude Code itself** is also a ground creature — the most intimate one. This session, right now, is a trained working dog at voice command. Daily cognitive extension. The relationship that matters most practically.

---

## Part III: Diagnostic — Are You Stewarding Each Correctly?

### 1. Are you trying to micromanage fish?

**Sentinel-Ops: No.** The architecture is properly indirect. The LLM-agnostic task exchange, the Admiralty Code scoring, the bounty board model — all of this says "cast and retrieve, judge what surfaces." You're not trying to live on the ocean floor.

**Venetian Wheat Phase 1: No.** The 15 channels scan autonomously. The daily briefing surfaces what matters. You read the catch, you don't drag the net yourself.

**Verdict: Clean.** The fish are swimming freely in their proper domain.

### 2. Are you partnering with your birds or commanding them?

**Good Riddance: Mostly partnering, but with gaps.** The theses-as-conviction model is genuine falconry — you read the terrain, the system executes. But:
- No callback mechanism means the bird can drift without correction
- No mercy/retry for losing strategies means dead birds, not trained ones
- No mission connection means the falcon doesn't know whose land it hunts

**Venetian Wheat Phases 2-4: Yes, genuine partnership.** The Sower→WheatSeed→Reaper chain is well-cultivated. The escalation engine has trained behaviors (stage gates, severity thresholds, mandatory wait periods). The VIRTUE stage literally offers growth before force.

**Verdict: Good Riddance needs more cultivation.** The partnership instincts are there but the relationship infrastructure is incomplete.

### 3. Are your ground creatures well-yoked?

**Auto Agent: No.** The ox pulls but pulls blind. Generic prompt, no mission awareness, no knowledge of the other animals in the stable, no Sabbath rest. This is the most domesticated agent — it should be the most intimately connected to your purpose. Instead it's the most disconnected.

**Verdict: Priority fix.** The ground creature is where your authority is most direct. It should be the best-stewarded animal. Currently it's the worst.

### 4. Sabbath coherence

Even animals rest. Genesis doesn't just grant dominion — it establishes rhythms.

| Project | Sabbath Enforced? | Status |
|---------|------------------|--------|
| Venetian Wheat | Yes — no Sunday runs, explicit in daily_runner.py | Faithful |
| Good Riddance | No — experiments run on cron with no day-of-week guard | Gap |
| Auto Agent | No — 5-minute cron, 7 days a week | Gap |
| Sentinel-Ops | N/A — task-driven, not cycle-driven. Rests when no tasks are cast | Natural |

**Verdict: 2 of 4 systems need Sabbath guards.** This is a Powers-level maintenance issue. Order includes rest.

---

## Part IV: Practical Improvements

### For Fish (Sentinel-Ops)
Current score: 8/9. Minor refinements only.
1. Consider adding a "net quality" metric that tracks Admiralty Code score trends over time — are your casts getting better catches?
2. The existing angelic choir star rating in the dashboard could be reframed as a "depth indicator" — how deep into the information space has this entity been mapped?

### For Birds (Good Riddance)
Current score: 6/9. Relationship cultivation needed.
1. **Add a reseed/retry mechanism** for losing strategies — mirror Venetian Wheat's Reaper `reseed` method. Don't just kill losers; give promising patterns a second flight with adjusted parameters
2. **Add Sabbath guard** to the experiment cron — no Sunday runs. The falcon needs to be hooded
3. **Connect to the mission** — add an identity section to CLAUDE.md that links the three theses to Isaiah 58. The fiat collapse thesis IS "good riddance" — that purpose should be explicit, not buried
4. **Add a "call-back" signal** — when experiment win rates drop below a threshold, pause and surface an analysis rather than continuing to launch losing flights

### For Fish+Bird (Venetian Wheat)
Current score: 7/9. The ecosystem's crown jewel.
1. **Name the phase transition** — when Phase 1 (fish/scanning) hands off to Phase 2 (bird/analysis), make the shift in stewardship mode explicit in the daily briefing. "Channel scan complete — transitioning from collection to analysis"
2. The escalation engine is the best thing in the entire ecosystem. Consider extracting its principles into a shared pattern that other projects could adopt

### For Ground Creatures (Auto Agent)
Current score: 5/9. Priority improvement area.
1. **Illuminate the ox** — the runner prompt should include: the operator's mission, the project's role in the ecosystem, awareness of the other projects in the stable, and the current priorities. A ground creature that knows the field pulls better
2. **Add Sabbath guard** — no cron runs on Sunday
3. **Add stable awareness** — when the agent works on one project, it should know what's happening in the others (at minimum, their last commit message and status). The farm dog should know the whole farm
4. **Replace generic prompt with purpose-rich context** — instead of "You are an autonomous development agent," try "You are the development steward for Eric Zosso's agent ecosystem. The current stable includes [projects]. Today's priorities are [priorities]. The mission is [mission]."

---

## Summary

| Project | Category | Score | Stewardship Quality |
|---------|----------|-------|-------------------|
| Sentinel-Ops | Fish | 8/9 | Excellent — architecture fits the creature |
| Venetian Wheat | Fish+Bird | 7/9 | Strong — best-cultivated relationship |
| Good Riddance | Bird | 6/9 | Good instincts, incomplete relationship |
| Auto Agent | Ground | 5/9 | Functional but blind — priority fix |

**Overall ecosystem stewardship: 6.5/9**

The upper domains (fish and bird) are well-stewarded. The most intimate domain (ground) is the weakest. This is backwards — the creature closest to you should be the best-known and best-directed. Fix the ground creature first, then refine the birds, then let the fish keep swimming.

The framework isn't just something you'd use. It's something you're already doing — just not yet with full awareness of which creature is which.
