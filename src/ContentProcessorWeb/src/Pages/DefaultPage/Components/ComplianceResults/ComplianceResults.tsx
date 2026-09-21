// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

import React from "react";
import {
  Badge,
  Button,
  Divider,
  makeStyles,
  Text,
  tokens,
} from "@fluentui/react-components";

type ValidationStatus = "pass" | "fail" | "missing" | "not_applicable" | "error";

interface RuleValidationResult {
  rule_id: string;
  status: ValidationStatus;
  severity: "critical" | "high" | "medium" | "low";
  expected?: unknown;
  actual?: unknown;
  unit?: string | null;
  message: string;
}

interface EntityValidationResult {
  entity_id: string;
  name: string;
  section: string;
  status: ValidationStatus;
  source_text?: string | null;
  source_page?: number | null;
  evidence_match_type?: "exact" | "contains" | "fuzzy" | "not_found";
  evidence_match_confidence?: number;
  source_regions?: {
    page_number: number;
    polygon: { x: number; y: number }[];
  }[];
  rule_results: RuleValidationResult[];
}

interface ValidationResult {
  rule_set_id: string;
  rule_set_version: string;
  summary: {
    passed: number;
    failed: number;
    missing: number;
    not_applicable: number;
    errors: number;
  };
  entities: EntityValidationResult[];
}

interface SkippedValidationResult {
  status: "skipped";
  reason: string;
}

interface ExtractionComparisonItem {
  Field?: string | null;
  Confidence?: string | null;
}

export interface ComplianceResultsProps {
  readonly validationResult?: ValidationResult | SkippedValidationResult | null;
  readonly comparisonItems?: ExtractionComparisonItem[];
  readonly isLoading?: boolean;
  readonly onViewSource?: (entity: EntityValidationResult) => void;
}

const useStyles = makeStyles({
  root: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    padding: "12px",
  },
  summary: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
    alignItems: "center",
  },
  ruleSet: {
    color: tokens.colorNeutralForeground3,
  },
  entityCard: {
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    borderLeftWidth: "4px",
    borderRadius: tokens.borderRadiusMedium,
    padding: "12px",
  },
  passCard: {
    borderLeftColor: tokens.colorPaletteGreenBorderActive,
  },
  failureCard: {
    borderLeftColor: tokens.colorPaletteRedBorderActive,
    backgroundColor: tokens.colorPaletteRedBackground1,
  },
  warningCard: {
    borderLeftColor: tokens.colorPaletteDarkOrangeBorderActive,
    backgroundColor: tokens.colorPaletteDarkOrangeBackground1,
  },
  neutralCard: {
    borderLeftColor: tokens.colorNeutralStroke1,
  },
  entityHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: "12px",
  },
  heading: {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
  },
  badges: {
    display: "flex",
    flexWrap: "wrap",
    justifyContent: "flex-end",
    gap: "6px",
  },
  evidence: {
    marginTop: "10px",
    padding: "8px",
    backgroundColor: tokens.colorNeutralBackground2,
    borderRadius: tokens.borderRadiusSmall,
    whiteSpace: "pre-wrap",
  },
  rules: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    marginTop: "10px",
  },
  rule: {
    display: "grid",
    gridTemplateColumns: "minmax(90px, 0.8fr) minmax(120px, 1fr) minmax(120px, 1fr)",
    gap: "8px",
    alignItems: "start",
  },
  label: {
    color: tokens.colorNeutralForeground3,
    display: "block",
    marginBottom: "2px",
  },
  empty: {
    padding: "24px",
    textAlign: "center",
    color: tokens.colorNeutralForeground2,
  },
});

const statusLabel: Record<ValidationStatus, string> = {
  pass: "Pass",
  fail: "Fail",
  missing: "Missing",
  not_applicable: "Not applicable",
  error: "Error",
};

const normalizeFieldName = (value: string): string =>
  value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");

export const findEntityConfidence = (
  entityId: string,
  items: ExtractionComparisonItem[] = [],
): string | null => {
  const normalizedEntityId = normalizeFieldName(entityId);
  const match = items.find(
    (item) =>
      typeof item.Field === "string" &&
      normalizeFieldName(item.Field) === normalizedEntityId,
  );
  return typeof match?.Confidence === "string" ? match.Confidence : null;
};

const formatValue = (value: unknown, unit?: string | null): string => {
  if (value === undefined || value === null || value === "") {
    return "Not provided";
  }
  const formatted = typeof value === "string" ? value : JSON.stringify(value);
  return unit ? `${formatted} ${unit}` : formatted;
};

const ComplianceResults: React.FC<ComplianceResultsProps> = ({
  validationResult,
  comparisonItems = [],
  isLoading = false,
  onViewSource,
}) => {
  const styles = useStyles();

  if (isLoading) {
    return <div className={styles.empty}>Loading compliance results...</div>;
  }

  if (!validationResult) {
    return <div className={styles.empty}>No compliance results available.</div>;
  }

  if (!("summary" in validationResult)) {
    return <div className={styles.empty}>{validationResult.reason}</div>;
  }

  const cardClass = (status: ValidationStatus) => {
    if (status === "fail" || status === "missing") return styles.failureCard;
    if (status === "error") return styles.warningCard;
    if (status === "pass") return styles.passCard;
    return styles.neutralCard;
  };

  return (
    <div className={styles.root}>
      <div className={styles.summary} aria-label="Compliance summary">
        <Badge color="success">Passed {validationResult.summary.passed}</Badge>
        <Badge color="danger">Failed {validationResult.summary.failed}</Badge>
        <Badge color="danger">Missing {validationResult.summary.missing}</Badge>
        <Badge color="informative">
          Not applicable {validationResult.summary.not_applicable}
        </Badge>
        <Badge color="warning">Errors {validationResult.summary.errors}</Badge>
        <Text size={200} className={styles.ruleSet}>
          Rules {validationResult.rule_set_id} v{validationResult.rule_set_version}
        </Text>
      </div>

      {validationResult.entities.map((entity) => {
        const confidence = findEntityConfidence(entity.entity_id, comparisonItems);
        return (
          <section
            key={entity.entity_id}
            className={`${styles.entityCard} ${cardClass(entity.status)}`}
            aria-label={`${entity.name}: ${statusLabel[entity.status]}`}
          >
            <div className={styles.entityHeader}>
              <div className={styles.heading}>
                <Text weight="semibold">{entity.name}</Text>
                <Text size={200}>{entity.section}</Text>
              </div>
              <div className={styles.badges}>
                <Badge
                  color={
                    entity.status === "pass"
                      ? "success"
                      : entity.status === "fail" || entity.status === "missing"
                        ? "danger"
                        : entity.status === "error"
                          ? "warning"
                          : "informative"
                  }
                >
                  {statusLabel[entity.status]}
                </Badge>
                <Badge appearance="outline">
                  Confidence: {confidence ?? "Unavailable"}
                </Badge>
              </div>
            </div>

            <div className={styles.evidence}>
              <Text size={200} className={styles.label}>Source evidence</Text>
              <Text>{entity.source_text || "No source evidence found."}</Text>
              {entity.source_page != null && (
                <Text size={200}> Page {entity.source_page}</Text>
              )}
              {entity.source_regions && entity.source_regions.length > 0 ? (
                <Button
                  appearance="subtle"
                  size="small"
                  onClick={() => onViewSource?.(entity)}
                >
                  View in source
                </Button>
              ) : entity.source_text ? (
                <Text size={200}> Source highlight unavailable</Text>
              ) : null}
            </div>

            <div className={styles.rules}>
              {entity.rule_results.map((rule, index) => (
                <React.Fragment key={rule.rule_id}>
                  {index > 0 && <Divider />}
                  <div className={styles.rule}>
                    <div>
                      <Text size={200} className={styles.label}>Rule</Text>
                      <Badge
                        color={
                          rule.status === "pass"
                            ? "success"
                            : rule.status === "fail" || rule.status === "missing"
                              ? "danger"
                              : rule.status === "error"
                                ? "warning"
                                : "informative"
                        }
                      >
                        {statusLabel[rule.status]}
                      </Badge>
                      <Text size={200}> {rule.severity}</Text>
                    </div>
                    <div>
                      <Text size={200} className={styles.label}>Expected</Text>
                      <Text>{formatValue(rule.expected, rule.unit)}</Text>
                    </div>
                    <div>
                      <Text size={200} className={styles.label}>Actual</Text>
                      <Text>{formatValue(rule.actual, rule.unit)}</Text>
                    </div>
                  </div>
                  <Text size={200}>{rule.message}</Text>
                </React.Fragment>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
};

export default ComplianceResults;
