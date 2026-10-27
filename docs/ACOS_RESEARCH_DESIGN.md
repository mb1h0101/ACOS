# ACOS research design — classroom orchestration first

## Educational problem

The target setting is a real secondary-school Mac classroom. Traditional screen broadcast can make students passive; once control is released, students can leave the intended learning activity. ACOS therefore does not aim to be a firewall, surveillance product, or reward/punishment system.

The instructional objective is to let students keep operating independently inside a teacher-defined digital boundary while the teacher can change that boundary in real time for the whole class, several students, or one student. A temporary attention intervention must be reversible so students can immediately continue their original work.

## Theoretical positioning

ACOS is positioned as a classroom orchestration system. Dillenbourg (2013) defines classroom orchestration around teachers' real-time management of multiple activities and constraints. Later reviews distinguish functions such as teacher awareness, class instruction, and student coordination, and report that teacher awareness is an important moderator of effectiveness.

The design implication for ACOS is that the Teacher Console should minimize orchestration load and expose actionable teaching levers rather than technical network configuration.

Key references:
- Dillenbourg, P. (2013). Design for classroom orchestration. *Computers & Education, 69*, 485–492. https://doi.org/10.1016/j.compedu.2013.04.013
- Feng, S., Zhang, L., Wang, S., & Cai, Z. (2023). Effectiveness of the functions of classroom orchestration systems: A systematic review and meta-analysis. *Computers & Education, 203*, 104864. https://doi.org/10.1016/j.compedu.2023.104864
- Kaliisa, R., Jivet, I., & Prinsloo, P. (2023). A checklist to guide the planning, designing, implementation, and evaluation of learning analytics dashboards. *International Journal of Educational Technology in Higher Education, 20*, 28. https://doi.org/10.1186/s41239-023-00394-6

## Research questions

RQ1. How can a teacher-facing orchestration interface support real-time transitions among whole-class, selected-student, and individual digital learning boundaries without interrupting students' ongoing work?

RQ2. To what extent can ACOS reduce orchestration load during technology-enhanced lessons, measured through interaction steps, intervention latency, failed/repeated control actions, and teacher-reported workload/usability?

RQ3. How do reversible digital-boundary interventions affect off-task foreground navigation, task completion, and the continuity of student work while preserving student autonomy inside the permitted environment?

These are research questions, not current outcome claims.

## Interface design derived from the RQs

The primary Teacher Console has exactly three decisions:
1. **Who?** Whole class or selected students.
2. **What should they be able to do right now?** Free operation, use only specified learning resources, or temporarily avoid specified resources.
3. **Do I need their attention now?** A reversible "look at teacher / continue" intervention.

Technical concepts such as DNS, domains, CDN, API endpoints, allow-list syntax, mode names, and network packages are not primary teacher-facing controls.

The teacher may enter a familiar service word such as `Google`, an ordinary URL, or an App name. ACOS evaluates only the student's current foreground browser host/App. It does not infer "necessary" background domains and does not claim packet-level firewall enforcement.

## Operational data for a paper

Collect only what is needed for classroom-orchestration evaluation:
- target scope: class / selected students;
- orchestration action and timestamp;
- command and mode-transition latency;
- overlay success/failure and recovery;
- online/reconnect status;
- foreground policy-intervention counts (aggregated/anonymized);
- task completion / first-attempt accuracy only when the lesson actually contains those tasks;
- teacher action count per activity transition;
- teacher-reported usability/orchestration load after the lesson.

Do not treat CI/load-test results as classroom learning outcomes.

## Evaluation sequence

1. Technical acceptance: one teacher Mac + one student Mac.
2. Small classroom pilot: verify target selection, reversible attention, resource boundary, reconnect, and no stale overlay.
3. Real lessons: collect operational logs plus teacher observations.
4. Only after appropriate ethics/consent requirements are satisfied should minor students' learning data be used for formal effectiveness claims.

## Paper contribution

The defensible contribution is not "ACOS blocks websites accurately." It is:

> A teacher-centered classroom orchestration approach that translates moment-to-moment instructional intent into reversible, targetable digital environment policies on student Macs, while preserving autonomous work inside the permitted boundary.

The paper should evaluate orchestrability and real classroom use, not advertise ACOS as a network-security product.
