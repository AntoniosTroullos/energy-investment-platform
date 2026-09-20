import { NextResponse } from "next/server";
import {
  evaluateMockScenario,
  type ScenarioEvaluationRequest,
} from "../../../lib/scenario/scenario.api";
import { isScenario } from "../../../lib/scenario/scenario.utils";

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as Partial<ScenarioEvaluationRequest>;

    if (!body.scenario || !isScenario(body.scenario)) {
      return NextResponse.json(
        { error: "Invalid scenario payload" },
        { status: 400 },
      );
    }

    const response = evaluateMockScenario({
      scenario: body.scenario,
    });

    return NextResponse.json(response);
  } catch {
    return NextResponse.json(
      { error: "Unable to evaluate scenario" },
      { status: 400 },
    );
  }
}
