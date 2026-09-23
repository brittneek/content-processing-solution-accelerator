// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

import React from "react";
import {
  Accordion,
  AccordionHeader,
  AccordionItem,
  AccordionPanel,
  Badge,
  Button,
  Divider,
  makeStyles,
  Text,
  tokens,
} from "@fluentui/react-components";

type ValidationStatus = "pass" | "fail" | "missing" | "not_applicable" | "error";
type ComplianceStatus =
  | "compliant"
  | "partially_compliant"
  | "noncompliant"
  | "undetermined"
  | "not_applicable"
  | "review_required";

interface RuleValidationResult {
  rule_id: string;
  path?: string;
  operator?: string;
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
  compliance_status?: ComplianceStatus;
  baseline?: string | null;
  extracted_value?: unknown;
  confidence?: number | null;
  minimum_confidence?: number | null;
  justification?: string | null;
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
  overall_status?: ComplianceStatus;
  summary: {
    passed: number;
    failed: number;
    missing: number;
    not_applicable: number;
    errors: number;
    compliant?: number;
    partially_compliant?: number;
    noncompliant?: number;
    undetermined?: number;
    compliance_not_applicable?: number;
    review_required?: number;
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
    position: "sticky",
    top: 0,
    zIndex: 2,
    padding: "10px 12px",
    margin: "-12px -12px 0",
    backgroundColor: tokens.colorNeutralBackground1,
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    boxShadow: tokens.shadow4,
  },
  ruleSet: {
    color: tokens.colorNeutralForeground3,
  },
  entityList: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  entityCard: {
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    borderLeftWidth: "4px",
    borderRadius: tokens.borderRadiusMedium,
    overflow: "hidden",
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
    flexWrap: "wrap",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: "12px",
    width: "100%",
    padding: "4px 0",
  },
  heading: {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
    minWidth: 0,
  },
  badges: {
    display: "flex",
    flexWrap: "wrap",
    justifyContent: "flex-end",
    gap: "6px",
    marginLeft: "auto",
    maxWidth: "100%",
  },
  evidence: {
    marginTop: "10px",
    padding: "8px",
    backgroundColor: tokens.colorNeutralBackground2,
    borderRadius: tokens.borderRadiusSmall,
    whiteSpace: "pre-wrap",
  },
  reviewGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: "12px",
    marginTop: "12px",
    "@media (max-width: 900px)": {
      gridTemplateColumns: "1fr",
    },
  },
  reviewColumn: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    gap: "6px",
    minWidth: 0,
    overflow: "hidden",
    padding: "10px",
    backgroundColor: tokens.colorNeutralBackground2,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusSmall,
  },
  contentText: {
    display: "block",
    maxWidth: "100%",
    whiteSpace: "pre-wrap",
    overflowWrap: "anywhere",
    wordBreak: "break-word",
  },
  rules: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    marginTop: "10px",
  },
  entityDetails: {
    paddingBottom: "12px",
  },
  rule: {
    display: "grid",
    gridTemplateColumns: "minmax(90px, 0.8fr) minmax(120px, 1fr) minmax(120px, 1fr)",
    gap: "8px",
    alignItems: "start",
    "@media (max-width: 700px)": {
      gridTemplateColumns: "1fr",
    },
  },
  ruleCell: {
    minWidth: 0,
    overflow: "hidden",
  },
  ruleIdentity: {
    display: "block",
    marginTop: "4px",
    overflowWrap: "anywhere",
  },
  label: {
    color: tokens.colorNeutralForeground3,
    display: "block",
    marginBottom: "2px",
  },
  formattedValue: {
    display: "block",
    maxWidth: "100%",
    whiteSpace: "pre-wrap",
    overflowWrap: "anywhere",
    wordBreak: "break-word",
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

const complianceStatusLabel: Record<ComplianceStatus, string> = {
  compliant: "Compliant",
  partially_compliant: "Partially compliant",
  noncompliant: "Noncompliant",
  undetermined: "Undetermined",
  not_applicable: "Not applicable",
  review_required: "Review required",
};

const legacyComplianceStatus = (status: ValidationStatus): ComplianceStatus => {
  if (status === "pass") return "compliant";
  if (status === "fail") return "noncompliant";
  if (status === "missing") return "undetermined";
  if (status === "error") return "review_required";
  return "not_applicable";
};

const complianceBadgeColor = (status: ComplianceStatus) => {
  if (status === "compliant") return "success" as const;
  if (status === "noncompliant") return "danger" as const;
  if (status === "partially_compliant" || status === "undetermined" || status === "review_required") {
    return "warning" as const;
  }
  return "informative" as const;
};

const normalizeFieldName = (value: string): string =>
  value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");

const formatRuleName = (rule: RuleValidationResult): string => {
  const identifier = rule.path ?? rule.rule_id;
  const segment = identifier.split(".").at(-1) ?? identifier;
  const words = segment.replace(/[_-]+/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
};

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

const formatValueLabel = (value: string): string => {
  const words = value.replace(/[_-]+/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
};

const formatScalarValue = (value: unknown, unit?: string | null): string => {
  if (value === undefined || value === null || value === "") {
    return "Not provided";
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  const formatted = String(value);
  return unit ? `${formatted} ${unit}` : formatted;
};

const formatValue = (value: unknown, unit?: string | null): string => {
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return "Not provided";
    }
    return value
      .map((item, index) => `${index + 1}. ${formatValue(item)}`)
      .join("\n");
  }
  if (typeof value === "object" && value !== null) {
    return Object.entries(value)
      .map(
        ([key, item]) =>
          `${formatValueLabel(key)}: ${formatValue(item)}`,
      )
      .join(", ");
  }
  return formatScalarValue(value, unit);
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

  const cardClass = (status: ComplianceStatus) => {
    if (status === "noncompliant") return styles.failureCard;
    if (
      status === "partially_compliant" ||
      status === "undetermined" ||
      status === "review_required"
    ) return styles.warningCard;
    if (status === "compliant") return styles.passCard;
    return styles.neutralCard;
  };

  return (
    <div className={styles.root}>
      <div className={styles.summary} aria-label="Compliance summary">
        <Badge color="success">
          Compliant {validationResult.summary.compliant ?? validationResult.summary.passed}
        </Badge>
        <Badge color="warning">
          Partial {validationResult.summary.partially_compliant ?? 0}
        </Badge>
        <Badge color="danger">
          Noncompliant {validationResult.summary.noncompliant ?? validationResult.summary.failed}
        </Badge>
        <Badge color="warning">
          Undetermined {validationResult.summary.undetermined ?? validationResult.summary.missing}
        </Badge>
        <Badge color="informative">
          Not applicable{" "}
          {validationResult.summary.compliance_not_applicable ??
            validationResult.summary.not_applicable}
        </Badge>
        <Badge color="warning">
          Review required {validationResult.summary.review_required ?? validationResult.summary.errors}
        </Badge>
        {validationResult.overall_status && (
          <Badge color={complianceBadgeColor(validationResult.overall_status)}>
            Overall: {complianceStatusLabel[validationResult.overall_status]}
          </Badge>
        )}
        <Text size={200} className={styles.ruleSet}>
          Rules {validationResult.rule_set_id} v{validationResult.rule_set_version}
        </Text>
      </div>

      <Accordion
        multiple
        collapsible
        defaultOpenItems={validationResult.entities.map(
          (entity) => entity.entity_id,
        )}
        className={styles.entityList}
      >
        {validationResult.entities.map((entity) => {
          const reviewerStatus =
            entity.compliance_status ?? legacyComplianceStatus(entity.status);
          const comparisonConfidence = findEntityConfidence(
            entity.entity_id,
            comparisonItems,
          );
          const confidence =
            typeof entity.confidence === "number"
              ? `${Math.round(entity.confidence * 100)}%`
              : comparisonConfidence;
          return (
            <AccordionItem
              key={entity.entity_id}
              value={entity.entity_id}
              className={`${styles.entityCard} ${cardClass(reviewerStatus)}`}
            >
              <AccordionHeader
                aria-label={`${entity.name}: ${complianceStatusLabel[reviewerStatus]}`}
              >
                <div className={styles.entityHeader}>
                  <div className={styles.heading}>
                    <Text weight="semibold">{entity.name}</Text>
                    <Text size={200}>{entity.section}</Text>
                  </div>
                  <div className={styles.badges}>
                    <Badge color={complianceBadgeColor(reviewerStatus)}>
                      {complianceStatusLabel[reviewerStatus]}
                    </Badge>
                    <Badge appearance="outline">
                      Confidence: {confidence ?? "Unavailable"}
                    </Badge>
                  </div>
                </div>
              </AccordionHeader>

              <AccordionPanel>
                <div className={styles.entityDetails}>
                  <div className={styles.reviewGrid}>
                    <div className={styles.reviewColumn}>
                      <Text size={200} weight="semibold" className={styles.label}>
                        Baseline requirement
                      </Text>
                      <Text className={styles.contentText}>
                        {entity.baseline || entity.name}
                      </Text>
                    </div>
                    <div className={styles.reviewColumn}>
                      <Text size={200} weight="semibold" className={styles.label}>
                        Extracted evidence
                      </Text>
                      <Text className={styles.contentText}>
                        {entity.source_text ||
                          formatValue(entity.extracted_value)}
                      </Text>
                      {entity.source_page != null && (
                        <Text size={200}> Page {entity.source_page}</Text>
                      )}
                      {entity.source_regions &&
                      entity.source_regions.length > 0 ? (
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
                    <div className={styles.reviewColumn}>
                      <Text size={200} weight="semibold" className={styles.label}>
                        Assessment
                      </Text>
                      <Badge color={complianceBadgeColor(reviewerStatus)}>
                        {complianceStatusLabel[reviewerStatus]}
                      </Badge>
                      <Text className={styles.contentText}>
                        {entity.justification ||
                          entity.rule_results
                            .map((rule) => rule.message)
                            .join(" ")}
                      </Text>
                    </div>
                  </div>

                  <div className={styles.rules}>
                    {entity.rule_results.map((rule, index) => (
                      <React.Fragment key={rule.rule_id}>
                        {index > 0 && <Divider />}
                        <div className={styles.rule}>
                          <div className={styles.ruleCell}>
                            <Text size={200} className={styles.label}>
                              Rule
                            </Text>
                            <Badge
                              color={
                                rule.status === "pass"
                                  ? "success"
                                  : rule.status === "fail" ||
                                      rule.status === "missing"
                                    ? "danger"
                                    : rule.status === "error"
                                      ? "warning"
                                      : "informative"
                              }
                            >
                              {statusLabel[rule.status]}
                            </Badge>
                            <Text size={200}> {rule.severity}</Text>
                            <Text
                              weight="semibold"
                              className={styles.ruleIdentity}
                            >
                              {formatRuleName(rule)}
                            </Text>
                            <Text size={100} className={styles.ruleIdentity}>
                              {rule.path ?? rule.rule_id}
                            </Text>
                          </div>
                          <div className={styles.ruleCell}>
                            <Text size={200} className={styles.label}>
                              Expected
                            </Text>
                            <Text className={styles.formattedValue}>
                              {formatValue(rule.expected, rule.unit)}
                            </Text>
                          </div>
                          <div className={styles.ruleCell}>
                            <Text size={200} className={styles.label}>
                              Actual
                            </Text>
                            <Text className={styles.formattedValue}>
                              {formatValue(rule.actual, rule.unit)}
                            </Text>
                          </div>
                        </div>
                        <Text size={200} className={styles.contentText}>
                          {rule.message}
                        </Text>
                      </React.Fragment>
                    ))}
                  </div>
                </div>
              </AccordionPanel>
            </AccordionItem>
          );
        })}
      </Accordion>
    </div>
  );
};

export default ComplianceResults;
