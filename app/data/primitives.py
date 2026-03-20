"""
48 Universal Skill Primitives — the vocabulary of USKill.
Each primitive has:
  - 6D feature vector  {temporal, spatial, cognitive, action, social, physical}
  - category           one of 6 categories
  - domain_impls       concrete implementation string per domain
  - metadata           complexity, reversible, inputs, outputs
"""

from typing import TypedDict

FeatureVector = dict[str, float]

CATEGORIES = ["PERCEPTION", "COGNITION", "ACTION", "CONTROL", "COMMUNICATION", "LEARNING"]

DOMAIN_KEYS = [
    "robotics_sim", "robotics_real", "software_dev",
    "education", "medical", "finance", "logistics", "game_ai",
]


class PrimitiveDef(TypedDict):
    id: str
    name: str
    category: str
    desc: str
    complexity: str
    reversible: bool
    inputs: list[str]
    outputs: list[str]
    features: FeatureVector
    domains: dict[str, dict[str, str]]  # domain_key → {impl, cost}


# fmt: off
PRIMITIVES: list[PrimitiveDef] = [
    # ── PERCEPTION (8) ─────────────────────────────────────────────
    {
        "id": "sense_state", "name": "sense_state", "category": "PERCEPTION",
        "desc": "Observe current environment or system state snapshot.",
        "complexity": "O(1)", "reversible": False,
        "inputs": ["sensor_id", "context"], "outputs": ["state_snapshot"],
        "features": {"temporal": 0.20, "spatial": 0.80, "cognitive": 0.30, "action": 0.20, "social": 0.10, "physical": 0.75},
        "domains": {
            "robotics_sim":  {"impl": "sim.read_sensor()",        "cost": "0.5ms"},
            "robotics_real": {"impl": "hw_sensor.read()",         "cost": "2ms"},
            "software_dev":  {"impl": "system.get_state()",       "cost": "5ms"},
            "education":     {"impl": "assessment.snapshot()",    "cost": "100ms"},
            "medical":       {"impl": "vitals.read()",            "cost": "50ms"},
            "finance":       {"impl": "feed.subscribe()",         "cost": "0.1ms"},
            "logistics":     {"impl": "wms.query_state()",        "cost": "10ms"},
            "game_ai":       {"impl": "game.observe()",           "cost": "0.1ms"},
        },
    },
    {
        "id": "detect_pattern", "name": "detect_pattern", "category": "PERCEPTION",
        "desc": "Identify recurring structures or anomalies in an observation stream.",
        "complexity": "O(n log n)", "reversible": False,
        "inputs": ["observation_stream", "pattern_spec"], "outputs": ["pattern_matches", "confidence"],
        "features": {"temporal": 0.60, "spatial": 0.55, "cognitive": 0.70, "action": 0.10, "social": 0.20, "physical": 0.30},
        "domains": {
            "robotics_sim":  {"impl": "sim.detect_pattern()",     "cost": "5ms"},
            "robotics_real": {"impl": "cv.match_template()",      "cost": "20ms"},
            "software_dev":  {"impl": "regex.findall()",          "cost": "1ms"},
            "education":     {"impl": "behavior.detect()",        "cost": "500ms"},
            "medical":       {"impl": "ecg.analyze()",            "cost": "100ms"},
            "finance":       {"impl": "signal.scan()",            "cost": "1ms"},
            "logistics":     {"impl": "route.pattern()",          "cost": "50ms"},
            "game_ai":       {"impl": "ai.find_pattern()",        "cost": "2ms"},
        },
    },
    {
        "id": "classify_object", "name": "classify_object", "category": "PERCEPTION",
        "desc": "Assign a categorical label to an observed entity.",
        "complexity": "O(n)", "reversible": False,
        "inputs": ["observation", "label_set"], "outputs": ["label", "confidence"],
        "features": {"temporal": 0.20, "spatial": 0.75, "cognitive": 0.80, "action": 0.10, "social": 0.20, "physical": 0.45},
        "domains": {
            "robotics_sim":  {"impl": "sim.classify()",           "cost": "10ms"},
            "robotics_real": {"impl": "model.infer()",            "cost": "50ms"},
            "software_dev":  {"impl": "classifier.predict()",     "cost": "20ms"},
            "education":     {"impl": "rubric.classify()",        "cost": "200ms"},
            "medical":       {"impl": "dx.classify()",            "cost": "500ms"},
            "finance":       {"impl": "asset.classify()",         "cost": "5ms"},
            "logistics":     {"impl": "sku.classify()",           "cost": "10ms"},
            "game_ai":       {"impl": "entity.tag()",             "cost": "1ms"},
        },
    },
    {
        "id": "measure_distance", "name": "measure_distance", "category": "PERCEPTION",
        "desc": "Compute distance or similarity between two entities in feature space.",
        "complexity": "O(d)", "reversible": False,
        "inputs": ["entity_a", "entity_b", "metric"], "outputs": ["distance", "similarity"],
        "features": {"temporal": 0.10, "spatial": 0.85, "cognitive": 0.60, "action": 0.05, "social": 0.15, "physical": 0.70},
        "domains": {
            "robotics_sim":  {"impl": "sim.euclidean()",          "cost": "0.1ms"},
            "robotics_real": {"impl": "lidar.measure()",          "cost": "5ms"},
            "software_dev":  {"impl": "math.dist()",              "cost": "0.1ms"},
            "education":     {"impl": "similarity.cosine()",      "cost": "50ms"},
            "medical":       {"impl": "anatomy.measure()",        "cost": "100ms"},
            "finance":       {"impl": "correlation.compute()",    "cost": "1ms"},
            "logistics":     {"impl": "geo.haversine()",          "cost": "0.5ms"},
            "game_ai":       {"impl": "vec.distance()",           "cost": "0.1ms"},
        },
    },
    {
        "id": "track_change", "name": "track_change", "category": "PERCEPTION",
        "desc": "Monitor an entity over time and detect significant transitions.",
        "complexity": "O(t)", "reversible": False,
        "inputs": ["entity", "baseline", "delta_threshold"], "outputs": ["change_events", "trend"],
        "features": {"temporal": 0.85, "spatial": 0.40, "cognitive": 0.55, "action": 0.10, "social": 0.20, "physical": 0.35},
        "domains": {
            "robotics_sim":  {"impl": "sim.track()",              "cost": "1ms"},
            "robotics_real": {"impl": "imu.track()",              "cost": "5ms"},
            "software_dev":  {"impl": "diff.watch()",             "cost": "2ms"},
            "education":     {"impl": "progress.track()",         "cost": "500ms"},
            "medical":       {"impl": "monitor.alert()",          "cost": "200ms"},
            "finance":       {"impl": "tick.subscribe()",         "cost": "0.1ms"},
            "logistics":     {"impl": "tracking.update()",        "cost": "100ms"},
            "game_ai":       {"impl": "entity.observe()",         "cost": "0.5ms"},
        },
    },
    {
        "id": "read_signal", "name": "read_signal", "category": "PERCEPTION",
        "desc": "Parse and decode incoming data signals or event streams.",
        "complexity": "O(n)", "reversible": False,
        "inputs": ["signal_source", "format"], "outputs": ["decoded_data"],
        "features": {"temporal": 0.70, "spatial": 0.20, "cognitive": 0.50, "action": 0.15, "social": 0.25, "physical": 0.20},
        "domains": {
            "robotics_sim":  {"impl": "sim.read_topic()",         "cost": "0.5ms"},
            "robotics_real": {"impl": "uart.read()",              "cost": "1ms"},
            "software_dev":  {"impl": "api.parse_response()",     "cost": "10ms"},
            "education":     {"impl": "input.parse()",            "cost": "100ms"},
            "medical":       {"impl": "ecg.decode()",             "cost": "50ms"},
            "finance":       {"impl": "feed.parse()",             "cost": "0.1ms"},
            "logistics":     {"impl": "rfid.scan()",              "cost": "20ms"},
            "game_ai":       {"impl": "event.poll()",             "cost": "0.1ms"},
        },
    },
    {
        "id": "segment_scene", "name": "segment_scene", "category": "PERCEPTION",
        "desc": "Partition a complex environment into discrete labeled regions.",
        "complexity": "O(n²)", "reversible": False,
        "inputs": ["scene_data", "segmentation_params"], "outputs": ["regions", "labels"],
        "features": {"temporal": 0.15, "spatial": 0.95, "cognitive": 0.65, "action": 0.05, "social": 0.10, "physical": 0.60},
        "domains": {
            "robotics_sim":  {"impl": "sim.segment()",            "cost": "20ms"},
            "robotics_real": {"impl": "pcl.segment()",            "cost": "80ms"},
            "software_dev":  {"impl": "parser.tokenize()",        "cost": "5ms"},
            "education":     {"impl": "content.section()",        "cost": "200ms"},
            "medical":       {"impl": "image.segment()",          "cost": "500ms"},
            "finance":       {"impl": "portfolio.bucket()",       "cost": "5ms"},
            "logistics":     {"impl": "zone.partition()",         "cost": "50ms"},
            "game_ai":       {"impl": "map.region()",             "cost": "2ms"},
        },
    },
    {
        "id": "estimate_pose", "name": "estimate_pose", "category": "PERCEPTION",
        "desc": "Infer 6-DoF position and orientation of entity in a reference frame.",
        "complexity": "O(n)", "reversible": False,
        "inputs": ["sensor_data", "reference_frame"], "outputs": ["pose_6dof", "uncertainty"],
        "features": {"temporal": 0.30, "spatial": 0.95, "cognitive": 0.55, "action": 0.10, "social": 0.05, "physical": 0.85},
        "domains": {
            "robotics_sim":  {"impl": "sim.get_pose()",           "cost": "1ms"},
            "robotics_real": {"impl": "slam.localize()",          "cost": "50ms"},
            "software_dev":  {"impl": "layout.compute()",         "cost": "10ms"},
            "education":     {"impl": "spatial.orient()",         "cost": "500ms"},
            "medical":       {"impl": "imaging.localize()",       "cost": "200ms"},
            "finance":       {"impl": "market.position()",        "cost": "1ms"},
            "logistics":     {"impl": "gps.localize()",           "cost": "100ms"},
            "game_ai":       {"impl": "agent.locate()",           "cost": "0.5ms"},
        },
    },

    # ── COGNITION (8) ───────────────────────────────────────────────
    {
        "id": "evaluate_condition", "name": "evaluate_condition", "category": "COGNITION",
        "desc": "Test whether a logical condition holds in the current state.",
        "complexity": "O(1)", "reversible": False,
        "inputs": ["condition_expr", "state"], "outputs": ["result", "confidence"],
        "features": {"temporal": 0.20, "spatial": 0.10, "cognitive": 0.90, "action": 0.05, "social": 0.15, "physical": 0.05},
        "domains": {
            "robotics_sim":  {"impl": "sim.check()",              "cost": "0.1ms"},
            "robotics_real": {"impl": "controller.assert()",      "cost": "1ms"},
            "software_dev":  {"impl": "assert_condition()",       "cost": "0.1ms"},
            "education":     {"impl": "quiz.check_answer()",      "cost": "100ms"},
            "medical":       {"impl": "criteria.evaluate()",      "cost": "50ms"},
            "finance":       {"impl": "rule.fire()",              "cost": "0.5ms"},
            "logistics":     {"impl": "rule.check()",             "cost": "5ms"},
            "game_ai":       {"impl": "condition.eval()",         "cost": "0.1ms"},
        },
    },
    {
        "id": "rank_options", "name": "rank_options", "category": "COGNITION",
        "desc": "Order a set of candidates by expected utility, quality, or reward.",
        "complexity": "O(n log n)", "reversible": False,
        "inputs": ["options", "utility_fn"], "outputs": ["ranked_options", "scores"],
        "features": {"temporal": 0.35, "spatial": 0.20, "cognitive": 0.90, "action": 0.20, "social": 0.30, "physical": 0.10},
        "domains": {
            "robotics_sim":  {"impl": "policy.rank()",            "cost": "5ms"},
            "robotics_real": {"impl": "planner.rank()",           "cost": "20ms"},
            "software_dev":  {"impl": "sorter.rank()",            "cost": "1ms"},
            "education":     {"impl": "exercise.rank()",          "cost": "200ms"},
            "medical":       {"impl": "treatment.rank()",         "cost": "1s"},
            "finance":       {"impl": "portfolio.rank()",         "cost": "10ms"},
            "logistics":     {"impl": "route.rank()",             "cost": "100ms"},
            "game_ai":       {"impl": "move.eval()",              "cost": "2ms"},
        },
    },
    {
        "id": "predict_outcome", "name": "predict_outcome", "category": "COGNITION",
        "desc": "Forecast future state from a proposed action sequence.",
        "complexity": "O(n·d)", "reversible": False,
        "inputs": ["action_sequence", "current_state", "horizon"], "outputs": ["predicted_state", "confidence"],
        "features": {"temporal": 0.80, "spatial": 0.40, "cognitive": 0.95, "action": 0.30, "social": 0.25, "physical": 0.35},
        "domains": {
            "robotics_sim":  {"impl": "sim.rollout()",            "cost": "50ms"},
            "robotics_real": {"impl": "model.predict()",          "cost": "100ms"},
            "software_dev":  {"impl": "simulator.run()",          "cost": "20ms"},
            "education":     {"impl": "outcome.predict()",        "cost": "500ms"},
            "medical":       {"impl": "prognosis.model()",        "cost": "2s"},
            "finance":       {"impl": "pnl.forecast()",           "cost": "50ms"},
            "logistics":     {"impl": "eta.predict()",            "cost": "200ms"},
            "game_ai":       {"impl": "lookahead.search()",       "cost": "10ms"},
        },
    },
    {
        "id": "detect_anomaly", "name": "detect_anomaly", "category": "COGNITION",
        "desc": "Identify observations that deviate significantly from expected baseline.",
        "complexity": "O(n)", "reversible": False,
        "inputs": ["observation", "baseline_model"], "outputs": ["anomaly_flag", "score", "location"],
        "features": {"temporal": 0.65, "spatial": 0.45, "cognitive": 0.85, "action": 0.10, "social": 0.20, "physical": 0.30},
        "domains": {
            "robotics_sim":  {"impl": "sim.anomaly()",            "cost": "5ms"},
            "robotics_real": {"impl": "sensor.check_outlier()",   "cost": "10ms"},
            "software_dev":  {"impl": "metrics.alert()",          "cost": "2ms"},
            "education":     {"impl": "behavior.flag()",          "cost": "200ms"},
            "medical":       {"impl": "vitals.anomaly()",         "cost": "100ms"},
            "finance":       {"impl": "fraud.detect()",           "cost": "5ms"},
            "logistics":     {"impl": "shipment.anomaly()",       "cost": "50ms"},
            "game_ai":       {"impl": "cheat.detect()",           "cost": "1ms"},
        },
    },
    {
        "id": "infer_intent", "name": "infer_intent", "category": "COGNITION",
        "desc": "Infer the goal of an observed agent using theory-of-mind modelling.",
        "complexity": "O(n²)", "reversible": False,
        "inputs": ["agent_actions", "context"], "outputs": ["inferred_goal", "confidence"],
        "features": {"temporal": 0.55, "spatial": 0.35, "cognitive": 0.95, "action": 0.15, "social": 0.85, "physical": 0.20},
        "domains": {
            "robotics_sim":  {"impl": "sim.infer_goal()",         "cost": "10ms"},
            "robotics_real": {"impl": "human.model_intent()",     "cost": "50ms"},
            "software_dev":  {"impl": "user.infer_action()",      "cost": "20ms"},
            "education":     {"impl": "student.infer_need()",     "cost": "500ms"},
            "medical":       {"impl": "patient.infer_state()",    "cost": "1s"},
            "finance":       {"impl": "market.sentiment()",       "cost": "100ms"},
            "logistics":     {"impl": "customer.predict()",       "cost": "200ms"},
            "game_ai":       {"impl": "opponent.model()",         "cost": "5ms"},
        },
    },
    {
        "id": "remember_context", "name": "remember_context", "category": "COGNITION",
        "desc": "Retrieve the k most relevant past experiences from memory.",
        "complexity": "O(n)", "reversible": False,
        "inputs": ["query", "memory_store", "k"], "outputs": ["context_items", "relevance_scores"],
        "features": {"temporal": 0.70, "spatial": 0.20, "cognitive": 0.90, "action": 0.05, "social": 0.35, "physical": 0.10},
        "domains": {
            "robotics_sim":  {"impl": "sim.recall()",             "cost": "5ms"},
            "robotics_real": {"impl": "memory.retrieve()",        "cost": "10ms"},
            "software_dev":  {"impl": "cache.fetch()",            "cost": "1ms"},
            "education":     {"impl": "portfolio.recall()",       "cost": "200ms"},
            "medical":       {"impl": "ehr.retrieve()",           "cost": "500ms"},
            "finance":       {"impl": "history.query()",          "cost": "10ms"},
            "logistics":     {"impl": "order.history()",          "cost": "50ms"},
            "game_ai":       {"impl": "memory.lookup()",          "cost": "1ms"},
        },
    },
    {
        "id": "plan_sequence", "name": "plan_sequence", "category": "COGNITION",
        "desc": "Generate an ordered action sequence to achieve a goal from current state.",
        "complexity": "O(b^d)", "reversible": False,
        "inputs": ["goal", "current_state", "constraints"], "outputs": ["action_plan", "cost"],
        "features": {"temporal": 0.60, "spatial": 0.50, "cognitive": 0.95, "action": 0.40, "social": 0.30, "physical": 0.35},
        "domains": {
            "robotics_sim":  {"impl": "planner.solve()",          "cost": "100ms"},
            "robotics_real": {"impl": "motion.plan()",            "cost": "500ms"},
            "software_dev":  {"impl": "scheduler.plan()",         "cost": "50ms"},
            "education":     {"impl": "curriculum.design()",      "cost": "2s"},
            "medical":       {"impl": "care.plan()",              "cost": "5s"},
            "finance":       {"impl": "strategy.build()",         "cost": "500ms"},
            "logistics":     {"impl": "route.plan()",             "cost": "1s"},
            "game_ai":       {"impl": "a_star.search()",          "cost": "20ms"},
        },
    },
    {
        "id": "resolve_conflict", "name": "resolve_conflict", "category": "COGNITION",
        "desc": "Arbitrate between competing objectives or resource claims.",
        "complexity": "O(n²)", "reversible": False,
        "inputs": ["conflicts", "priority_fn"], "outputs": ["resolution", "rationale"],
        "features": {"temporal": 0.40, "spatial": 0.20, "cognitive": 0.90, "action": 0.30, "social": 0.75, "physical": 0.15},
        "domains": {
            "robotics_sim":  {"impl": "sim.arbitrate()",          "cost": "10ms"},
            "robotics_real": {"impl": "controller.resolve()",     "cost": "20ms"},
            "software_dev":  {"impl": "conflict.resolve()",       "cost": "5ms"},
            "education":     {"impl": "mediation.resolve()",      "cost": "1s"},
            "medical":       {"impl": "triage.prioritize()",      "cost": "500ms"},
            "finance":       {"impl": "risk.adjudicate()",        "cost": "50ms"},
            "logistics":     {"impl": "dispatch.arbitrate()",     "cost": "100ms"},
            "game_ai":       {"impl": "conflict.settle()",        "cost": "5ms"},
        },
    },

    # ── ACTION (6) ──────────────────────────────────────────────────
    {
        "id": "move_to_target", "name": "move_to_target", "category": "ACTION",
        "desc": "Navigate to or reposition toward a specified target location.",
        "complexity": "O(n log n)", "reversible": True,
        "inputs": ["target_location", "motion_params"], "outputs": ["trajectory", "arrival_time"],
        "features": {"temporal": 0.50, "spatial": 0.95, "cognitive": 0.40, "action": 0.90, "social": 0.15, "physical": 0.90},
        "domains": {
            "robotics_sim":  {"impl": "sim.move_to()",            "cost": "10ms"},
            "robotics_real": {"impl": "base.navigate()",          "cost": "varies"},
            "software_dev":  {"impl": "cursor.move()",            "cost": "1ms"},
            "education":     {"impl": "student.engage()",         "cost": "5s"},
            "medical":       {"impl": "instrument.position()",    "cost": "2s"},
            "finance":       {"impl": "order.route()",            "cost": "5ms"},
            "logistics":     {"impl": "vehicle.dispatch()",       "cost": "varies"},
            "game_ai":       {"impl": "agent.pathfind()",         "cost": "5ms"},
        },
    },
    {
        "id": "apply_force", "name": "apply_force", "category": "ACTION",
        "desc": "Exert controlled physical force or torque on a target object.",
        "complexity": "O(1)", "reversible": False,
        "inputs": ["target", "force_vector", "duration"], "outputs": ["applied_force", "result_state"],
        "features": {"temporal": 0.20, "spatial": 0.80, "cognitive": 0.25, "action": 0.95, "social": 0.05, "physical": 0.98},
        "domains": {
            "robotics_sim":  {"impl": "sim.apply_force()",        "cost": "0.5ms"},
            "robotics_real": {"impl": "gripper.grip()",           "cost": "500ms"},
            "software_dev":  {"impl": "request.push()",           "cost": "5ms"},
            "education":     {"impl": "exercise.apply()",         "cost": "varies"},
            "medical":       {"impl": "procedure.apply()",        "cost": "varies"},
            "finance":       {"impl": "order.execute()",          "cost": "10ms"},
            "logistics":     {"impl": "lift.operate()",           "cost": "2s"},
            "game_ai":       {"impl": "physics.impulse()",        "cost": "0.5ms"},
        },
    },
    {
        "id": "execute_sequence", "name": "execute_sequence", "category": "ACTION",
        "desc": "Run a pre-planned sequence of sub-actions with failure monitoring.",
        "complexity": "O(n)", "reversible": False,
        "inputs": ["action_sequence", "rollback_policy"], "outputs": ["execution_log", "final_state"],
        "features": {"temporal": 0.65, "spatial": 0.55, "cognitive": 0.50, "action": 0.90, "social": 0.20, "physical": 0.65},
        "domains": {
            "robotics_sim":  {"impl": "sim.execute()",            "cost": "varies"},
            "robotics_real": {"impl": "arm.execute_plan()",       "cost": "varies"},
            "software_dev":  {"impl": "pipeline.run()",           "cost": "varies"},
            "education":     {"impl": "lesson.deliver()",         "cost": "varies"},
            "medical":       {"impl": "protocol.execute()",       "cost": "varies"},
            "finance":       {"impl": "strategy.execute()",       "cost": "varies"},
            "logistics":     {"impl": "workflow.execute()",       "cost": "varies"},
            "game_ai":       {"impl": "script.run()",             "cost": "varies"},
        },
    },
    {
        "id": "modify_state", "name": "modify_state", "category": "ACTION",
        "desc": "Apply a targeted validated transformation to system state attributes.",
        "complexity": "O(1)", "reversible": True,
        "inputs": ["target_field", "new_value", "validation_fn"], "outputs": ["old_value", "success"],
        "features": {"temporal": 0.25, "spatial": 0.30, "cognitive": 0.45, "action": 0.80, "social": 0.25, "physical": 0.40},
        "domains": {
            "robotics_sim":  {"impl": "sim.set_param()",          "cost": "0.1ms"},
            "robotics_real": {"impl": "controller.set()",         "cost": "5ms"},
            "software_dev":  {"impl": "state.update()",           "cost": "0.5ms"},
            "education":     {"impl": "grade.update()",           "cost": "100ms"},
            "medical":       {"impl": "record.update()",          "cost": "1s"},
            "finance":       {"impl": "position.update()",        "cost": "5ms"},
            "logistics":     {"impl": "inventory.update()",       "cost": "50ms"},
            "game_ai":       {"impl": "world.mutate()",           "cost": "0.1ms"},
        },
    },
    {
        "id": "emit_output", "name": "emit_output", "category": "ACTION",
        "desc": "Produce an artifact, signal, or structured communication as output.",
        "complexity": "O(n)", "reversible": False,
        "inputs": ["output_spec", "target_channel"], "outputs": ["artifact", "delivery_status"],
        "features": {"temporal": 0.40, "spatial": 0.25, "cognitive": 0.50, "action": 0.75, "social": 0.60, "physical": 0.20},
        "domains": {
            "robotics_sim":  {"impl": "sim.publish()",            "cost": "0.5ms"},
            "robotics_real": {"impl": "actuator.signal()",        "cost": "2ms"},
            "software_dev":  {"impl": "response.send()",          "cost": "5ms"},
            "education":     {"impl": "feedback.send()",          "cost": "500ms"},
            "medical":       {"impl": "report.send()",            "cost": "5s"},
            "finance":       {"impl": "trade.confirm()",          "cost": "10ms"},
            "logistics":     {"impl": "notification.send()",      "cost": "100ms"},
            "game_ai":       {"impl": "event.emit()",             "cost": "0.1ms"},
        },
    },
    {
        "id": "release_resource", "name": "release_resource", "category": "ACTION",
        "desc": "Free a held resource, lock, or exclusive capability.",
        "complexity": "O(1)", "reversible": False,
        "inputs": ["resource_handle"], "outputs": ["release_status"],
        "features": {"temporal": 0.15, "spatial": 0.20, "cognitive": 0.20, "action": 0.70, "social": 0.15, "physical": 0.50},
        "domains": {
            "robotics_sim":  {"impl": "sim.release()",            "cost": "0.1ms"},
            "robotics_real": {"impl": "gripper.open()",           "cost": "200ms"},
            "software_dev":  {"impl": "lock.release()",           "cost": "0.1ms"},
            "education":     {"impl": "resource.return()",        "cost": "100ms"},
            "medical":       {"impl": "equipment.release()",      "cost": "2s"},
            "finance":       {"impl": "margin.free()",            "cost": "5ms"},
            "logistics":     {"impl": "dock.release()",           "cost": "5s"},
            "game_ai":       {"impl": "slot.free()",              "cost": "0.1ms"},
        },
    },

    {
        "id": "sample_environment", "name": "sample_environment", "category": "ACTION",
        "desc": "Actively probe the environment by executing a test action and observing the response.",
        "complexity": "O(k)", "reversible": True,
        "inputs": ["probe_action", "target", "sample_count"], "outputs": ["samples", "response_distribution"],
        "features": {"temporal": 0.45, "spatial": 0.70, "cognitive": 0.55, "action": 0.85, "social": 0.10, "physical": 0.65},
        "domains": {
            "robotics_sim":  {"impl": "sim.probe()",             "cost": "50ms"},
            "robotics_real": {"impl": "sensor.sample()",         "cost": "200ms"},
            "software_dev":  {"impl": "canary.test()",           "cost": "100ms"},
            "education":     {"impl": "probe.question()",        "cost": "2s"},
            "medical":       {"impl": "diagnostic.test()",       "cost": "5s"},
            "finance":       {"impl": "market.probe()",          "cost": "10ms"},
            "logistics":     {"impl": "scan.verify()",           "cost": "500ms"},
            "game_ai":       {"impl": "world.query()",           "cost": "1ms"},
        },
    },
    {
        "id": "queue_action", "name": "queue_action", "category": "ACTION",
        "desc": "Enqueue an action for deferred or asynchronous execution with priority.",
        "complexity": "O(log n)", "reversible": True,
        "inputs": ["action", "priority", "deadline"], "outputs": ["queue_position", "estimated_start"],
        "features": {"temporal": 0.75, "spatial": 0.15, "cognitive": 0.35, "action": 0.70, "social": 0.25, "physical": 0.15},
        "domains": {
            "robotics_sim":  {"impl": "sim.queue()",             "cost": "0.5ms"},
            "robotics_real": {"impl": "task_queue.push()",       "cost": "1ms"},
            "software_dev":  {"impl": "celery.delay()",          "cost": "2ms"},
            "education":     {"impl": "assignment.schedule()",   "cost": "100ms"},
            "medical":       {"impl": "procedure.schedule()",    "cost": "1s"},
            "finance":       {"impl": "order.queue()",           "cost": "0.5ms"},
            "logistics":     {"impl": "job.enqueue()",           "cost": "10ms"},
            "game_ai":       {"impl": "action.defer()",          "cost": "0.1ms"},
        },
    },
    # ── CONTROL (8) ─────────────────────────────────────────────────
    {
        "id": "loop_until", "name": "loop_until", "category": "CONTROL",
        "desc": "Repeat an action block until a termination condition or max iterations.",
        "complexity": "O(n)", "reversible": False,
        "inputs": ["action_fn", "termination_cond", "max_iter"], "outputs": ["iterations", "final_result"],
        "features": {"temporal": 0.70, "spatial": 0.25, "cognitive": 0.55, "action": 0.60, "social": 0.10, "physical": 0.30},
        "domains": {
            "robotics_sim":  {"impl": "sim.loop()",               "cost": "varies"},
            "robotics_real": {"impl": "control.while_loop()",     "cost": "varies"},
            "software_dev":  {"impl": "while loop",               "cost": "varies"},
            "education":     {"impl": "practice.repeat()",        "cost": "varies"},
            "medical":       {"impl": "therapy.session_loop()",   "cost": "varies"},
            "finance":       {"impl": "backtest.iterate()",       "cost": "varies"},
            "logistics":     {"impl": "conveyor.cycle()",         "cost": "varies"},
            "game_ai":       {"impl": "game_loop.tick()",         "cost": "1ms/iter"},
        },
    },
    {
        "id": "branch_on_condition", "name": "branch_on_condition", "category": "CONTROL",
        "desc": "Select an execution path based on a condition evaluation result.",
        "complexity": "O(1)", "reversible": False,
        "inputs": ["condition", "if_branch", "else_branch"], "outputs": ["selected_branch", "result"],
        "features": {"temporal": 0.20, "spatial": 0.10, "cognitive": 0.70, "action": 0.50, "social": 0.20, "physical": 0.10},
        "domains": {
            "robotics_sim":  {"impl": "sim.branch()",             "cost": "0.1ms"},
            "robotics_real": {"impl": "controller.if_else()",     "cost": "0.5ms"},
            "software_dev":  {"impl": "if/else",                  "cost": "0.1ms"},
            "education":     {"impl": "adaptive.branch()",        "cost": "100ms"},
            "medical":       {"impl": "decision.tree()",          "cost": "50ms"},
            "finance":       {"impl": "rule.branch()",            "cost": "0.5ms"},
            "logistics":     {"impl": "routing.branch()",         "cost": "5ms"},
            "game_ai":       {"impl": "fsm.transition()",         "cost": "0.1ms"},
        },
    },
    {
        "id": "retry_on_failure", "name": "retry_on_failure", "category": "CONTROL",
        "desc": "Re-attempt a failed action with configurable backoff and recovery.",
        "complexity": "O(r)", "reversible": False,
        "inputs": ["action_fn", "max_retries", "backoff_policy"], "outputs": ["result", "attempts"],
        "features": {"temporal": 0.75, "spatial": 0.15, "cognitive": 0.55, "action": 0.65, "social": 0.15, "physical": 0.25},
        "domains": {
            "robotics_sim":  {"impl": "sim.retry()",              "cost": "varies"},
            "robotics_real": {"impl": "controller.retry()",       "cost": "varies"},
            "software_dev":  {"impl": "tenacity.retry()",         "cost": "varies"},
            "education":     {"impl": "attempt.retry()",          "cost": "varies"},
            "medical":       {"impl": "procedure.retry()",        "cost": "varies"},
            "finance":       {"impl": "order.retry()",            "cost": "varies"},
            "logistics":     {"impl": "delivery.retry()",         "cost": "varies"},
            "game_ai":       {"impl": "action.retry()",           "cost": "varies"},
        },
    },
    {
        "id": "throttle_rate", "name": "throttle_rate", "category": "CONTROL",
        "desc": "Limit action frequency within resource or safety bounds.",
        "complexity": "O(1)", "reversible": False,
        "inputs": ["action_fn", "rate_limit", "burst"], "outputs": ["allowed", "wait_ms"],
        "features": {"temporal": 0.85, "spatial": 0.05, "cognitive": 0.35, "action": 0.55, "social": 0.20, "physical": 0.10},
        "domains": {
            "robotics_sim":  {"impl": "sim.rate_limit()",         "cost": "0.1ms"},
            "robotics_real": {"impl": "safety.throttle()",        "cost": "1ms"},
            "software_dev":  {"impl": "limiter.check()",          "cost": "0.5ms"},
            "education":     {"impl": "pacing.throttle()",        "cost": "100ms"},
            "medical":       {"impl": "dosage.limit()",           "cost": "10ms"},
            "finance":       {"impl": "order.rate_limit()",       "cost": "0.5ms"},
            "logistics":     {"impl": "throughput.cap()",         "cost": "5ms"},
            "game_ai":       {"impl": "cooldown.enforce()",       "cost": "0.1ms"},
        },
    },
    {
        "id": "synchronize", "name": "synchronize", "category": "CONTROL",
        "desc": "Coordinate timing between parallel actions or distributed agents.",
        "complexity": "O(n)", "reversible": False,
        "inputs": ["participants", "sync_point"], "outputs": ["synchronized", "latency"],
        "features": {"temporal": 0.90, "spatial": 0.30, "cognitive": 0.50, "action": 0.55, "social": 0.70, "physical": 0.20},
        "domains": {
            "robotics_sim":  {"impl": "sim.sync()",               "cost": "1ms"},
            "robotics_real": {"impl": "ros2.sync()",              "cost": "5ms"},
            "software_dev":  {"impl": "asyncio.gather()",         "cost": "varies"},
            "education":     {"impl": "class.sync()",             "cost": "5s"},
            "medical":       {"impl": "team.coordinate()",        "cost": "10s"},
            "finance":       {"impl": "settlement.sync()",        "cost": "100ms"},
            "logistics":     {"impl": "fleet.sync()",             "cost": "1s"},
            "game_ai":       {"impl": "tick.sync()",              "cost": "1ms"},
        },
    },
    {
        "id": "abort_on_threshold", "name": "abort_on_threshold", "category": "CONTROL",
        "desc": "Immediately halt execution when a safety metric exceeds a threshold.",
        "complexity": "O(1)", "reversible": False,
        "inputs": ["metric_fn", "threshold", "rollback_fn"], "outputs": ["aborted", "final_state"],
        "features": {"temporal": 0.30, "spatial": 0.10, "cognitive": 0.55, "action": 0.80, "social": 0.10, "physical": 0.35},
        "domains": {
            "robotics_sim":  {"impl": "sim.e_stop()",             "cost": "0.1ms"},
            "robotics_real": {"impl": "safety.e_stop()",          "cost": "1ms"},
            "software_dev":  {"impl": "circuit_breaker.open()",   "cost": "0.5ms"},
            "education":     {"impl": "safety.halt()",            "cost": "100ms"},
            "medical":       {"impl": "alarm.trigger()",          "cost": "10ms"},
            "finance":       {"impl": "stop_loss.trigger()",      "cost": "1ms"},
            "logistics":     {"impl": "hazmat.halt()",            "cost": "500ms"},
            "game_ai":       {"impl": "kill_switch.activate()",   "cost": "0.1ms"},
        },
    },

    {
        "id": "checkpoint", "name": "checkpoint", "category": "CONTROL",
        "desc": "Persist a recoverable snapshot of execution state at a safe point.",
        "complexity": "O(n)", "reversible": True,
        "inputs": ["state", "checkpoint_id", "storage"], "outputs": ["snapshot_ref", "timestamp"],
        "features": {"temporal": 0.60, "spatial": 0.20, "cognitive": 0.45, "action": 0.55, "social": 0.10, "physical": 0.20},
        "domains": {
            "robotics_sim":  {"impl": "sim.snapshot()",          "cost": "10ms"},
            "robotics_real": {"impl": "state.checkpoint()",      "cost": "50ms"},
            "software_dev":  {"impl": "db.savepoint()",          "cost": "5ms"},
            "education":     {"impl": "progress.save()",         "cost": "500ms"},
            "medical":       {"impl": "protocol.checkpoint()",   "cost": "2s"},
            "finance":       {"impl": "position.snapshot()",     "cost": "5ms"},
            "logistics":     {"impl": "route.checkpoint()",      "cost": "50ms"},
            "game_ai":       {"impl": "game.save()",             "cost": "100ms"},
        },
    },
    {
        "id": "escalate", "name": "escalate", "category": "CONTROL",
        "desc": "Hand off control to a higher-authority agent, human, or fallback policy.",
        "complexity": "O(1)", "reversible": False,
        "inputs": ["context", "escalation_target", "reason"], "outputs": ["escalation_id", "acknowledged"],
        "features": {"temporal": 0.30, "spatial": 0.10, "cognitive": 0.60, "action": 0.50, "social": 0.85, "physical": 0.05},
        "domains": {
            "robotics_sim":  {"impl": "sim.handoff()",           "cost": "1ms"},
            "robotics_real": {"impl": "hri.escalate()",          "cost": "5s"},
            "software_dev":  {"impl": "pagerduty.alert()",       "cost": "500ms"},
            "education":     {"impl": "instructor.escalate()",   "cost": "30s"},
            "medical":       {"impl": "senior.escalate()",       "cost": "60s"},
            "finance":       {"impl": "risk.escalate()",         "cost": "100ms"},
            "logistics":     {"impl": "supervisor.alert()",      "cost": "5s"},
            "game_ai":       {"impl": "override.trigger()",      "cost": "0.5ms"},
        },
    },
    # ── COMMUNICATION (8) ───────────────────────────────────────────
    {
        "id": "send_message", "name": "send_message", "category": "COMMUNICATION",
        "desc": "Transmit a structured message with delivery confirmation.",
        "complexity": "O(n)", "reversible": False,
        "inputs": ["message", "recipient", "channel"], "outputs": ["delivery_status", "message_id"],
        "features": {"temporal": 0.45, "spatial": 0.10, "cognitive": 0.40, "action": 0.65, "social": 0.90, "physical": 0.05},
        "domains": {
            "robotics_sim":  {"impl": "sim.publish_msg()",        "cost": "0.5ms"},
            "robotics_real": {"impl": "ros2.publish()",           "cost": "2ms"},
            "software_dev":  {"impl": "queue.publish()",          "cost": "1ms"},
            "education":     {"impl": "notification.send()",      "cost": "500ms"},
            "medical":       {"impl": "ehr.message()",            "cost": "2s"},
            "finance":       {"impl": "alert.send()",             "cost": "5ms"},
            "logistics":     {"impl": "sms.send()",               "cost": "200ms"},
            "game_ai":       {"impl": "chat.send()",              "cost": "0.5ms"},
        },
    },
    {
        "id": "request_input", "name": "request_input", "category": "COMMUNICATION",
        "desc": "Solicit information or a decision from an agent, user, or oracle.",
        "complexity": "O(1)", "reversible": False,
        "inputs": ["query", "responder", "timeout"], "outputs": ["response", "latency"],
        "features": {"temporal": 0.55, "spatial": 0.10, "cognitive": 0.60, "action": 0.30, "social": 0.90, "physical": 0.05},
        "domains": {
            "robotics_sim":  {"impl": "sim.request()",            "cost": "1ms"},
            "robotics_real": {"impl": "hri.ask()",                "cost": "5s"},
            "software_dev":  {"impl": "input_dialog.show()",      "cost": "varies"},
            "education":     {"impl": "quiz.prompt()",            "cost": "varies"},
            "medical":       {"impl": "consent.request()",        "cost": "10s"},
            "finance":       {"impl": "approval.request()",       "cost": "varies"},
            "logistics":     {"impl": "driver.confirm()",         "cost": "30s"},
            "game_ai":       {"impl": "player.prompt()",          "cost": "varies"},
        },
    },
    {
        "id": "broadcast_state", "name": "broadcast_state", "category": "COMMUNICATION",
        "desc": "Share a state subset with all subscribed agents in the network.",
        "complexity": "O(n)", "reversible": False,
        "inputs": ["state_subset", "subscribers"], "outputs": ["broadcast_id", "delivery_count"],
        "features": {"temporal": 0.50, "spatial": 0.20, "cognitive": 0.35, "action": 0.60, "social": 0.85, "physical": 0.05},
        "domains": {
            "robotics_sim":  {"impl": "sim.broadcast()",          "cost": "1ms"},
            "robotics_real": {"impl": "ros2.latched_topic()",     "cost": "5ms"},
            "software_dev":  {"impl": "event.emit()",             "cost": "1ms"},
            "education":     {"impl": "board.update()",           "cost": "2s"},
            "medical":       {"impl": "ehr.update()",             "cost": "5s"},
            "finance":       {"impl": "feed.push()",              "cost": "0.5ms"},
            "logistics":     {"impl": "dashboard.broadcast()",    "cost": "2s"},
            "game_ai":       {"impl": "state.sync()",             "cost": "0.1ms"},
        },
    },
    {
        "id": "negotiate", "name": "negotiate", "category": "COMMUNICATION",
        "desc": "Iterative exchange to converge on a mutually acceptable agreement.",
        "complexity": "O(r²)", "reversible": False,
        "inputs": ["proposal", "counterparty", "constraints"], "outputs": ["agreement", "rounds"],
        "features": {"temporal": 0.60, "spatial": 0.10, "cognitive": 0.80, "action": 0.40, "social": 0.95, "physical": 0.05},
        "domains": {
            "robotics_sim":  {"impl": "sim.negotiate()",          "cost": "10ms"},
            "robotics_real": {"impl": "hri.negotiate()",          "cost": "30s"},
            "software_dev":  {"impl": "protocol.handshake()",     "cost": "5ms"},
            "education":     {"impl": "peer.discuss()",           "cost": "5m"},
            "medical":       {"impl": "team.conference()",        "cost": "30m"},
            "finance":       {"impl": "order.negotiate()",        "cost": "100ms"},
            "logistics":     {"impl": "contract.negotiate()",     "cost": "varies"},
            "game_ai":       {"impl": "diplomacy.negotiate()",    "cost": "5ms"},
        },
    },
    {
        "id": "acknowledge", "name": "acknowledge", "category": "COMMUNICATION",
        "desc": "Confirm receipt and understanding of a message or command.",
        "complexity": "O(1)", "reversible": False,
        "inputs": ["message_id", "sender"], "outputs": ["ack_status"],
        "features": {"temporal": 0.25, "spatial": 0.05, "cognitive": 0.25, "action": 0.40, "social": 0.80, "physical": 0.05},
        "domains": {
            "robotics_sim":  {"impl": "sim.ack()",                "cost": "0.1ms"},
            "robotics_real": {"impl": "ros2.ack()",               "cost": "1ms"},
            "software_dev":  {"impl": "http.200()",               "cost": "1ms"},
            "education":     {"impl": "confirm.received()",       "cost": "500ms"},
            "medical":       {"impl": "order.acknowledge()",      "cost": "2s"},
            "finance":       {"impl": "trade.confirm()",          "cost": "10ms"},
            "logistics":     {"impl": "pod.sign()",               "cost": "5s"},
            "game_ai":       {"impl": "event.ack()",              "cost": "0.1ms"},
        },
    },

    {
        "id": "subscribe", "name": "subscribe", "category": "COMMUNICATION",
        "desc": "Register interest in a stream or topic to receive ongoing updates.",
        "complexity": "O(1)", "reversible": True,
        "inputs": ["topic", "handler_fn", "filter_spec"], "outputs": ["subscription_id", "backlog"],
        "features": {"temporal": 0.65, "spatial": 0.10, "cognitive": 0.30, "action": 0.35, "social": 0.75, "physical": 0.05},
        "domains": {
            "robotics_sim":  {"impl": "sim.subscribe()",         "cost": "0.5ms"},
            "robotics_real": {"impl": "ros2.subscriber()",       "cost": "1ms"},
            "software_dev":  {"impl": "event_bus.subscribe()",   "cost": "0.5ms"},
            "education":     {"impl": "feed.subscribe()",        "cost": "200ms"},
            "medical":       {"impl": "monitor.subscribe()",     "cost": "100ms"},
            "finance":       {"impl": "stream.subscribe()",      "cost": "0.1ms"},
            "logistics":     {"impl": "tracker.subscribe()",     "cost": "10ms"},
            "game_ai":       {"impl": "event.listen()",          "cost": "0.1ms"},
        },
    },
    {
        "id": "report_status", "name": "report_status", "category": "COMMUNICATION",
        "desc": "Publish a structured status report to monitoring or logging infrastructure.",
        "complexity": "O(1)", "reversible": False,
        "inputs": ["status_data", "channel", "level"], "outputs": ["report_id"],
        "features": {"temporal": 0.40, "spatial": 0.05, "cognitive": 0.30, "action": 0.45, "social": 0.70, "physical": 0.05},
        "domains": {
            "robotics_sim":  {"impl": "sim.log_status()",        "cost": "0.1ms"},
            "robotics_real": {"impl": "telemetry.report()",      "cost": "2ms"},
            "software_dev":  {"impl": "logger.info()",           "cost": "0.1ms"},
            "education":     {"impl": "dashboard.update()",      "cost": "500ms"},
            "medical":       {"impl": "chart.update()",          "cost": "2s"},
            "finance":       {"impl": "audit.log()",             "cost": "1ms"},
            "logistics":     {"impl": "status.push()",           "cost": "100ms"},
            "game_ai":       {"impl": "hud.update()",            "cost": "0.5ms"},
        },
    },
    {
        "id": "query_peer", "name": "query_peer", "category": "COMMUNICATION",
        "desc": "Send a structured query to a peer agent and await a typed response.",
        "complexity": "O(1)", "reversible": False,
        "inputs": ["peer_id", "query_payload", "timeout_ms"], "outputs": ["response", "latency_ms"],
        "features": {"temporal": 0.50, "spatial": 0.15, "cognitive": 0.55, "action": 0.35, "social": 0.90, "physical": 0.05},
        "domains": {
            "robotics_sim":  {"impl": "sim.service_call()",      "cost": "1ms"},
            "robotics_real": {"impl": "ros2.service()",          "cost": "5ms"},
            "software_dev":  {"impl": "rpc.call()",              "cost": "10ms"},
            "education":     {"impl": "peer.ask()",              "cost": "5s"},
            "medical":       {"impl": "consult.request()",       "cost": "30s"},
            "finance":       {"impl": "broker.query()",          "cost": "5ms"},
            "logistics":     {"impl": "dispatch.query()",        "cost": "200ms"},
            "game_ai":       {"impl": "agent.query()",           "cost": "1ms"},
        },
    },
    # ── LEARNING (8) ────────────────────────────────────────────
    {
        "id": "update_belief", "name": "update_belief", "category": "LEARNING",
        "desc": "Integrate new evidence into a model using Bayesian or gradient updates.",
        "complexity": "O(n)", "reversible": False,
        "inputs": ["evidence", "prior_belief", "learning_rate"], "outputs": ["posterior_belief", "kl_divergence"],
        "features": {"temporal": 0.60, "spatial": 0.20, "cognitive": 0.95, "action": 0.25, "social": 0.30, "physical": 0.10},
        "domains": {
            "robotics_sim":  {"impl": "belief.update()",          "cost": "10ms"},
            "robotics_real": {"impl": "filter.update()",          "cost": "50ms"},
            "software_dev":  {"impl": "model.train_step()",       "cost": "100ms"},
            "education":     {"impl": "assessment.update()",      "cost": "500ms"},
            "medical":       {"impl": "prior.update()",           "cost": "1s"},
            "finance":       {"impl": "signal.reweight()",        "cost": "50ms"},
            "logistics":     {"impl": "forecast.update()",        "cost": "200ms"},
            "game_ai":       {"impl": "policy.update()",          "cost": "5ms"},
        },
    },
    {
        "id": "store_example", "name": "store_example", "category": "LEARNING",
        "desc": "Persist a (state, action, outcome) tuple into long-term memory.",
        "complexity": "O(1)", "reversible": True,
        "inputs": ["state", "action", "outcome", "memory_store"], "outputs": ["example_id"],
        "features": {"temporal": 0.40, "spatial": 0.15, "cognitive": 0.65, "action": 0.40, "social": 0.20, "physical": 0.10},
        "domains": {
            "robotics_sim":  {"impl": "replay.add()",             "cost": "0.5ms"},
            "robotics_real": {"impl": "demo.record()",            "cost": "1ms"},
            "software_dev":  {"impl": "db.insert()",              "cost": "5ms"},
            "education":     {"impl": "portfolio.save()",         "cost": "500ms"},
            "medical":       {"impl": "case.save()",              "cost": "2s"},
            "finance":       {"impl": "trade.log()",              "cost": "1ms"},
            "logistics":     {"impl": "event.log()",              "cost": "100ms"},
            "game_ai":       {"impl": "buffer.push()",            "cost": "0.1ms"},
        },
    },
    {
        "id": "refine_model", "name": "refine_model", "category": "LEARNING",
        "desc": "Improve a predictive or decision model from an accumulated experience batch.",
        "complexity": "O(n²)", "reversible": False,
        "inputs": ["experience_batch", "model", "optimizer"], "outputs": ["improved_model", "loss"],
        "features": {"temporal": 0.70, "spatial": 0.20, "cognitive": 0.95, "action": 0.30, "social": 0.25, "physical": 0.10},
        "domains": {
            "robotics_sim":  {"impl": "sim.train()",              "cost": "5s"},
            "robotics_real": {"impl": "model.finetune()",         "cost": "1h"},
            "software_dev":  {"impl": "model.fit()",              "cost": "varies"},
            "education":     {"impl": "curriculum.adapt()",       "cost": "1h"},
            "medical":       {"impl": "protocol.refine()",        "cost": "1d"},
            "finance":       {"impl": "strategy.retrain()",       "cost": "1h"},
            "logistics":     {"impl": "predictor.retrain()",      "cost": "30m"},
            "game_ai":       {"impl": "agent.train()",            "cost": "10m"},
        },
    },
    {
        "id": "generalize_pattern", "name": "generalize_pattern", "category": "LEARNING",
        "desc": "Extract an abstract rule from examples that generalizes to novel instances.",
        "complexity": "O(n log n)", "reversible": False,
        "inputs": ["examples", "hypothesis_space"], "outputs": ["rule", "coverage"],
        "features": {"temporal": 0.55, "spatial": 0.30, "cognitive": 0.95, "action": 0.20, "social": 0.35, "physical": 0.10},
        "domains": {
            "robotics_sim":  {"impl": "sim.generalize()",         "cost": "1s"},
            "robotics_real": {"impl": "policy.generalize()",      "cost": "10s"},
            "software_dev":  {"impl": "ml.extract_rule()",        "cost": "1s"},
            "education":     {"impl": "concept.map()",            "cost": "5m"},
            "medical":       {"impl": "pattern.extract()",        "cost": "5s"},
            "finance":       {"impl": "alpha.abstract()",         "cost": "5s"},
            "logistics":     {"impl": "heuristic.derive()",       "cost": "2s"},
            "game_ai":       {"impl": "rule.learn()",             "cost": "500ms"},
        },
    },
    {
        "id": "forget_outdated", "name": "forget_outdated", "category": "LEARNING",
        "desc": "Prune stale knowledge to prevent catastrophic interference.",
        "complexity": "O(n)", "reversible": False,
        "inputs": ["memory_store", "staleness_fn", "retention_policy"], "outputs": ["pruned_count", "freed_capacity"],
        "features": {"temporal": 0.75, "spatial": 0.10, "cognitive": 0.70, "action": 0.45, "social": 0.15, "physical": 0.05},
        "domains": {
            "robotics_sim":  {"impl": "memory.prune()",           "cost": "10ms"},
            "robotics_real": {"impl": "buffer.evict()",           "cost": "50ms"},
            "software_dev":  {"impl": "cache.evict()",            "cost": "1ms"},
            "education":     {"impl": "curriculum.prune()",       "cost": "1s"},
            "medical":       {"impl": "records.archive()",        "cost": "5s"},
            "finance":       {"impl": "history.expire()",         "cost": "10ms"},
            "logistics":     {"impl": "log.rotate()",             "cost": "500ms"},
            "game_ai":       {"impl": "memory.forget()",          "cost": "5ms"},
        },
    },
    {
        "id": "transfer_knowledge", "name": "transfer_knowledge", "category": "LEARNING",
        "desc": "Apply source-domain representations to bootstrap target-domain learning.",
        "complexity": "O(n)", "reversible": False,
        "inputs": ["source_model", "target_domain", "adapter_map"], "outputs": ["adapted_model", "transfer_score"],
        "features": {"temporal": 0.50, "spatial": 0.35, "cognitive": 0.95, "action": 0.50, "social": 0.40, "physical": 0.15},
        "domains": {
            "robotics_sim":  {"impl": "sim.transfer()",           "cost": "10s"},
            "robotics_real": {"impl": "domain_adapt.apply()",     "cost": "1h"},
            "software_dev":  {"impl": "model.transfer()",         "cost": "1s"},
            "education":     {"impl": "skill.scaffold()",         "cost": "1d"},
            "medical":       {"impl": "protocol.transfer()",      "cost": "1d"},
            "finance":       {"impl": "alpha.port()",             "cost": "1h"},
            "logistics":     {"impl": "model.redeploy()",         "cost": "1h"},
            "game_ai":       {"impl": "agent.transfer()",         "cost": "30m"},
        },
    },
    {
        "id": "evaluate_policy", "name": "evaluate_policy", "category": "LEARNING",
        "desc": "Measure the performance of a policy or strategy against an evaluation metric.",
        "complexity": "O(n·k)", "reversible": False,
        "inputs": ["policy", "eval_env", "num_episodes"], "outputs": ["mean_reward", "variance", "metrics"],
        "features": {"temporal": 0.65, "spatial": 0.30, "cognitive": 0.90, "action": 0.40, "social": 0.20, "physical": 0.25},
        "domains": {
            "robotics_sim":  {"impl": "sim.evaluate()",          "cost": "10s"},
            "robotics_real": {"impl": "robot.benchmark()",       "cost": "1h"},
            "software_dev":  {"impl": "benchmark.run()",         "cost": "1m"},
            "education":     {"impl": "test.administer()",       "cost": "30m"},
            "medical":       {"impl": "protocol.evaluate()",     "cost": "1d"},
            "finance":       {"impl": "backtest.evaluate()",     "cost": "10m"},
            "logistics":     {"impl": "simulation.evaluate()",   "cost": "30m"},
            "game_ai":       {"impl": "tournament.run()",        "cost": "5m"},
        },
    },
    {
        "id": "explain_decision", "name": "explain_decision", "category": "LEARNING",
        "desc": "Generate a human-interpretable explanation for a decision or prediction.",
        "complexity": "O(n)", "reversible": False,
        "inputs": ["decision", "model", "context"], "outputs": ["explanation", "confidence", "factors"],
        "features": {"temporal": 0.25, "spatial": 0.15, "cognitive": 0.95, "action": 0.20, "social": 0.75, "physical": 0.05},
        "domains": {
            "robotics_sim":  {"impl": "sim.explain()",           "cost": "50ms"},
            "robotics_real": {"impl": "explainer.shap()",        "cost": "500ms"},
            "software_dev":  {"impl": "lime.explain()",          "cost": "200ms"},
            "education":     {"impl": "feedback.explain()",      "cost": "1s"},
            "medical":       {"impl": "dx.rationale()",          "cost": "5s"},
            "finance":       {"impl": "model.interpret()",       "cost": "100ms"},
            "logistics":     {"impl": "decision.trace()",        "cost": "200ms"},
            "game_ai":       {"impl": "ai.explain()",            "cost": "10ms"},
        },
    },
]

# ── Fast lookup indices ──────────────────────────────────────────────
PRIMITIVE_BY_ID: dict[str, PrimitiveDef] = {p["id"]: p for p in PRIMITIVES}
PRIMITIVES_BY_CATEGORY: dict[str, list[PrimitiveDef]] = {cat: [] for cat in CATEGORIES}
for _p in PRIMITIVES:
    PRIMITIVES_BY_CATEGORY[_p["category"]].append(_p)


def get_primitive(primitive_id: str) -> PrimitiveDef | None:
    return PRIMITIVE_BY_ID.get(primitive_id)


def get_feature_vector(primitive_id: str) -> FeatureVector | None:
    p = PRIMITIVE_BY_ID.get(primitive_id)
    return p["features"] if p else None


def get_impl(primitive_id: str, domain: str) -> str | None:
    p = PRIMITIVE_BY_ID.get(primitive_id)
    if not p:
        return None
    d = p["domains"].get(domain)
    return d["impl"] if d else None


def get_impl_cost(primitive_id: str, domain: str) -> str | None:
    p = PRIMITIVE_BY_ID.get(primitive_id)
    if not p:
        return None
    d = p["domains"].get(domain)
    return d["cost"] if d else None


def get_category(primitive_id: str) -> str | None:
    p = PRIMITIVE_BY_ID.get(primitive_id)
    return p["category"] if p else None


ALL_PRIMITIVE_IDS: list[str] = [p["id"] for p in PRIMITIVES]
# fmt: on
