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
  summary: {
    passed: 0,
    failed: 1,
    missing: 1,
    not_applicable: 0,
    errors: 0,
  },
  entities: [
    {
      entity_id: "maximum_temperature",
      name: "Maximum temperature",
      section: "Environment",
      status: "fail" as const,
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
          status: "fail" as const,
          severity: "high" as const,
          expected: 40,
          actual: 35,
          unit: "C",
          message: "Value must be at least 40 C.",
        },
      ],
    },
    {
      entity_id: "minimum_temperature",
      name: "Minimum temperature",
      section: "Environment",
      status: "missing" as const,
      source_text: null,
      source_page: null,
      rule_results: [
        {
          rule_id: "minimum-temperature-required",
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

    expect(screen.getByText("Failed 1")).toBeInTheDocument();
    expect(screen.getByText("Missing 1")).toBeInTheDocument();
    expect(screen.getByText("Maximum ambient temperature is 35 C.")).toBeInTheDocument();
    expect(screen.getByText("Confidence: High")).toBeInTheDocument();
    expect(screen.getByText("Confidence: Unavailable")).toBeInTheDocument();
    expect(screen.getByText("40 C")).toBeInTheDocument();
    expect(screen.getByText("35 C")).toBeInTheDocument();
    expect(screen.getByText("Page 8")).toBeInTheDocument();
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
});
