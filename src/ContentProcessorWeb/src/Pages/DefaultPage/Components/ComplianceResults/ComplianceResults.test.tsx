// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

import React from "react";
import { FluentProvider, webLightTheme } from "@fluentui/react-components";
import { render, screen } from "@testing-library/react";

import ComplianceResults, { findEntityConfidence } from "./ComplianceResults";
import userEvent from "@testing-library/user-event";

const renderComponent = (component: React.ReactElement) =>
  render(<FluentProvider theme={webLightTheme}>{component}</FluentProvider>);

const validationResult = {
  rule_set_id: "generator-global",
  rule_set_version: "0.1.0",
  overall_status: "noncompliant" as const,
  summary: {
    passed: 0,
    failed: 1,
    missing: 1,
    not_applicable: 0,
    errors: 0,
    compliant: 0,
    partially_compliant: 0,
    noncompliant: 1,
    undetermined: 1,
    compliance_not_applicable: 0,
    review_required: 0,
  },
  entities: [
    {
      entity_id: "maximum_temperature",
      name: "Maximum temperature",
      section: "Environment",
      status: "fail" as const,
      compliance_status: "noncompliant" as const,
      baseline: "The generator must operate at a minimum of 40 C.",
      extracted_value: 35,
      confidence: 0.94,
      minimum_confidence: 0.6,
      justification: "The submitted 35 C rating is below the required 40 C.",
      source_text: "Maximum ambient temperature is 35 C.",
      source_page: 8,
      evidence_match_type: "exact" as const,
      evidence_match_confidence: 1,
      source_regions: [
        {
          page_number: 8,
          polygon: [
            { x: 0.1, y: 0.2 },
            { x: 0.5, y: 0.2 },
            { x: 0.5, y: 0.3 },
          ],
        },
      ],
      rule_results: [
        {
          rule_id: "maximum-temperature-minimum",
          path: "environment.maximum_temperature_c",
          status: "fail" as const,
          severity: "high" as const,
          expected: 40,
          actual: 35,
          unit: "C",
          message: "Value must be at least 40 C.",
        },
        {
          rule_id: "load-test-points",
          path: "testing.load_points",
          status: "pass" as const,
          severity: "medium" as const,
          expected: [
            { load_percent: 50, with_fan: true },
            { load_percent: 75, with_fan: true },
            { load_percent: 100, with_fan: true },
          ],
          actual: [
            { load_percent: 50, with_fan: true },
            { load_percent: 75, with_fan: true },
            { load_percent: 100, with_fan: true },
          ],
          message: "All required load test points were provided.",
        },
      ],
    },
    {
      entity_id: "minimum_temperature",
      name: "Minimum temperature",
      section: "Environment",
      status: "missing" as const,
      compliance_status: "undetermined" as const,
      baseline: "The minimum temperature rating must be stated.",
      extracted_value: null,
      confidence: null,
      minimum_confidence: 0.6,
      justification: "The minimum temperature rating was not found.",
      source_text: null,
      source_page: null,
      rule_results: [
        {
          rule_id: "minimum-temperature-required",
          path: "environment.minimum_temperature_c",
          status: "missing" as const,
          severity: "high" as const,
          message: "A value is required.",
        },
      ],
    },
  ],
};

describe("ComplianceResults", () => {
  it("renders summary, failures, evidence, rules, and confidence separately", () => {
    renderComponent(
      <ComplianceResults
        validationResult={validationResult}
        comparisonItems={[
          { Field: "Maximum Temperature", Confidence: "High" },
        ]}
      />,
    );

    expect(screen.getByText("Noncompliant 1")).toBeInTheDocument();
    expect(screen.getByText("Undetermined 1")).toBeInTheDocument();
    expect(screen.getByText("Overall: Noncompliant")).toBeInTheDocument();
    expect(
      screen.getByText("The generator must operate at a minimum of 40 C."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("The submitted 35 C rating is below the required 40 C."),
    ).toBeInTheDocument();
    expect(screen.getByText("Maximum ambient temperature is 35 C.")).toBeInTheDocument();
    expect(screen.getByText("Confidence: 94%")).toBeInTheDocument();
    expect(screen.getByText("Confidence: Unavailable")).toBeInTheDocument();
    expect(screen.getByText("40 C")).toBeInTheDocument();
    expect(screen.getByText("35 C")).toBeInTheDocument();
    expect(
      screen.getByText("environment.maximum_temperature_c"),
    ).toBeInTheDocument();
    expect(screen.getByText("Maximum temperature c")).toBeInTheDocument();
    expect(screen.getByText("Page 8")).toBeInTheDocument();
    expect(
      screen.getAllByText(
        "1. Load percent: 50, With fan: Yes\n2. Load percent: 75, With fan: Yes\n3. Load percent: 100, With fan: Yes",
      ),
    ).toHaveLength(2);
  });

  it("explains when validation was skipped", () => {
    renderComponent(
      <ComplianceResults
        validationResult={{
          status: "skipped",
          reason: "The selected schema has no validation rules.",
        }}
      />,
    );

    expect(
      screen.getByText("The selected schema has no validation rules."),
    ).toBeInTheDocument();
  });

  it("matches confidence fields without relying on display punctuation", () => {
    expect(
      findEntityConfidence("maximum_temperature", [
        { Field: "Maximum Temperature", Confidence: "High" },
      ]),
    ).toBe("High");
  });

  it("selects resolved source evidence for highlighting", async () => {
    const onViewSource = jest.fn();
    renderComponent(
      <ComplianceResults
        validationResult={validationResult}
        onViewSource={onViewSource}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "View in source" }));
    expect(onViewSource).toHaveBeenCalledWith(validationResult.entities[0]);
  });

  it("allows each requirement to be collapsed independently", async () => {
    renderComponent(<ComplianceResults validationResult={validationResult} />);

    const maximumTemperature = screen.getByRole("button", {
      name: "Maximum temperature: Noncompliant",
    });
    const minimumTemperature = screen.getByRole("button", {
      name: "Minimum temperature: Undetermined",
    });

    expect(maximumTemperature).toHaveAttribute("aria-expanded", "true");
    expect(minimumTemperature).toHaveAttribute("aria-expanded", "true");

    await userEvent.click(maximumTemperature);

    expect(maximumTemperature).toHaveAttribute("aria-expanded", "false");
    expect(minimumTemperature).toHaveAttribute("aria-expanded", "true");
  });
});
