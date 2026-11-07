# Project brief: (name TBD)

The product spec: what we're building and why. It rarely changes. The living plan (scope, architecture, milestones, who's doing what) is in [project-plan.md](project-plan.md).

## Context

We're building this at Hack the Change 2026 (Calgary). There are two of us: Neel and Param. Stack: FastAPI backend, React frontend (details in the project plan).

Prompt we're answering (Prompt 2): "How can we leverage technology to help people develop in-demand skills and build meaningful networks in a rapidly changing job market?"

Judging criteria (we need at least "Satisfactory" on ALL of them to pass prescreening):

1. Innovation & Creativity
2. Impact & Relevance to Prompt
3. Feasibility & Scalability
4. Technical Execution (working prototype, technical depth, stability, appropriate stack)
5. User Experience & Design (intuitive, accessible, aesthetically pleasing)

Sidepots we're targeting:

- **Best Local Impact (Benevity):** real-world Calgary community impact
- **Best in Accessibility (Clio):** accessibility, inclusivity, user trust, privacy, transparency

Submission: Devpost, a 2–5 min demo video, and a public GitHub link. Judges WILL look at the repo.

## What we're building

A levels-based educational service that teaches people new to software engineering to program end to end, and to EARN their way up to using AI responsibly, without vibe coding.

## The problem

- New developers "git push and pray." AI tools (Cursor, Claude Code, Codex) produce code that works, but the developer has no idea what it does. When it breaks, they're stuck.
- AI-generated code often quietly compromises on security, and people who don't understand their code can't catch it.
- Junior roles are shrinking because AI now does entry-level work. To be hireable, new devs need what AI can't replace: understanding, debugging, security judgment, and breadth across the stack.

## Our thesis and differentiator (this shapes every design decision)

AI is a power tool, so you earn access to it. Beginners start with fundamentals and no AI code generation. As they prove understanding, they unlock more AI help, but only for grunt work. The learner always writes the core features.

Other tools give you the answer. Ours makes you understand, defend, and secure every line you ship, and it widens your skills across the full stack. Generic LLM "learning modes" are opt-in and easy to switch off. Ours is enforced in the workflow: your work isn't accepted until you prove you understand it.

## The level system

Each level has projects, an AI-permission policy, and a level-up gate.

- **Level 1, Foundations:** small projects (e.g. calculator, to-do app). NO AI code generation. The AI acts only as reviewer and tutor. Skills: language basics, git, PRs, reading errors, debugging.
- **Level 2, Full stack basics:** a small app with frontend + backend + database + auth. The AI can explain concepts and answer questions, but still writes no code for you.
- **Level 3, AI for grunt work:** on bigger projects, tickets are labelled CORE (you write it) or DELEGABLE (AI allowed: tests, boilerplate, styling, config). You must still review and explain any AI-written code you merge.
- **Level 4, Directing agents:** you design the architecture and own the core (e.g. the whole backend), and agents handle delegable layers (e.g. parts of the frontend, test suites). The skill being taught here is directing and reviewing AI output.
- **Level-up gates:** completed projects, comprehension-gate scores, and security issues found and fixed.

We can't police which tools someone uses locally. Enforcement comes from the comprehension gate. If you can't explain it, it doesn't merge, regardless of who wrote it.

## Core learning loop (every level)

1. Tickets explain the WHY and acceptance criteria, never the HOW. Tickets rotate across the stack to fill gaps in the learner's skill map.
2. The learner opens a PR, and the AI senior reviewer takes over:
   - **Socratic review:** questions and a graduated hint ladder (concept → where to look → small illustrative snippet). It NEVER posts full corrected code.
   - **Security review:** checks for common vulnerability classes (injection, hardcoded secrets, missing auth/authorization, unvalidated input, unsafe dependencies). It explains the class, and the learner must fix it AND explain the fix.
   - **Comprehension gate:** 2–3 AI-generated questions about the learner's OWN diff ("What happens if this input is empty?", "Why this approach?", "What does line N do?"). Graded by the AI. Fail = more hints, not approval.
   - **Policy check:** flags work that doesn't fit the level's AI policy or CORE/DELEGABLE labels.
3. The skill profile updates and progress toward the next level is shown.
4. **Experience report / portfolio:** a verifiable record of projects, levels, concepts demonstrated, and security fixes, for employers.

## MVP scope (build fully, in this priority order)

1. **LIVE GitHub loop** (MUST WORK, the demo's centerpiece): a Level 1 project PR → webhook → AI posts a Socratic review with at least one security or correctness finding → learner answers comprehension questions in our app → pass → PR approved, skill profile and level progress update.
2. **Level map:** all 4 levels visible, with the current one active and the higher ones locked (showing what each unlocks, including AI permissions).
3. **Learner dashboard:** skill map across the stack, current project and ticket, progress to the next level.
4. **Experience report / portfolio page.**

Seed or fake everything else (auth, signup, assessment, notifications).

## Later phases (do NOT build until the MVP works end to end)

- **Step 2:** Level 3–4 AI-delegation features (CORE/DELEGABLE ticket labels, agent integration, review of AI-written code).
- **Nonprofit commissions:** nonprofits post real work as tickets, and learners at higher levels take them on. Nonprofits struggle to find people willing to give hours of unpaid labor. This gives them a steady pipeline of motivated learners, gives learners real clients, and the AI reviews everything before it ships. This is our Calgary local-impact story.
- **Matched teams and volunteer pros:** cross-functional squads for large projects, plus industry devs and profs for short, high-value moments (design interviews, final reviews). This covers "networks."

## Non-negotiables

- We're a security-education product, so our own repo must be clean: secrets in .env (gitignored), no committed keys, input validation on our endpoints.
- Accessibility: semantic HTML, keyboard navigable, good contrast, labelled inputs, screen-reader friendly.
- Transparency and privacy: store minimal data. Show learners why the AI graded them the way it did, and let them flag a review they disagree with.
- Demo stability beats clever features. Use seeded data where it helps.
