"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ConfidenceIndicator } from "./confidence-indicator";
import type { ExtractedField } from "@/types/extraction";

interface CourseInfoProps {
  extraction: {
    course_name: ExtractedField<string>;
    course_code: ExtractedField<string | null> | null;
    instructor_name: ExtractedField<string | null> | null;
    instructor_email: ExtractedField<string | null> | null;
    office_hours: ExtractedField<string | null> | null;
  };
  onChange: (field: string, value: string) => void;
  hideConfidence?: boolean;
}

interface FieldRowProps {
  label: string;
  field: ExtractedField<string | null> | null;
  fieldKey: string;
  onChange: (field: string, value: string) => void;
  hideConfidence?: boolean;
}

function FieldRow({ label, field, fieldKey, onChange, hideConfidence }: FieldRowProps) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");

  if (!field) return null;

  const displayValue = field.value ?? "Not found";
  const isEmpty = field.value === null || field.value === "";

  function startEdit() {
    setEditValue(field!.value ?? "");
    setEditing(true);
  }

  function commitEdit() {
    setEditing(false);
    if (editValue !== (field!.value ?? "")) {
      onChange(fieldKey, editValue);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") commitEdit();
    if (e.key === "Escape") setEditing(false);
  }

  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0 flex-1">
        <p className="text-sm text-muted-foreground mb-1">{label}</p>
        {editing ? (
          <Input
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={commitEdit}
            onKeyDown={handleKeyDown}
            autoFocus
            className="h-8 text-sm"
          />
        ) : (
          <p
            className={`text-sm cursor-pointer rounded px-1 -mx-1 hover:bg-accent transition-colors ${isEmpty ? "text-muted-foreground italic" : ""}`}
            onClick={startEdit}
          >
            {displayValue}
          </p>
        )}
      </div>
      {!hideConfidence && (
        <ConfidenceIndicator
          confidence={field.confidence}
          sourceText={field.source_text}
          className="mt-5 shrink-0"
        />
      )}
    </div>
  );
}

export function CourseInfo({ extraction, onChange, hideConfidence }: CourseInfoProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Course Information</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 sm:grid-cols-2">
          <FieldRow
            label="Course Name"
            field={extraction.course_name}
            fieldKey="course_name"
            onChange={onChange}
            hideConfidence={hideConfidence}
          />
          <FieldRow
            label="Course Code"
            field={extraction.course_code}
            fieldKey="course_code"
            onChange={onChange}
            hideConfidence={hideConfidence}
          />
          <FieldRow
            label="Instructor"
            field={extraction.instructor_name}
            fieldKey="instructor_name"
            onChange={onChange}
            hideConfidence={hideConfidence}
          />
          <FieldRow
            label="Email"
            field={extraction.instructor_email}
            fieldKey="instructor_email"
            onChange={onChange}
            hideConfidence={hideConfidence}
          />
          <FieldRow
            label="Office Hours"
            field={extraction.office_hours}
            fieldKey="office_hours"
            onChange={onChange}
            hideConfidence={hideConfidence}
          />
        </div>
      </CardContent>
    </Card>
  );
}
