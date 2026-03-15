"use client";

import { useState } from "react";
import { format } from "date-fns";
import {
  AlertTriangle,
  CalendarIcon,
  Check,
  Pencil,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Calendar } from "@/components/ui/calendar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ConfidenceIndicator } from "./confidence-indicator";
import { AssessmentEditDialog } from "./assessment-edit-dialog";
import { cn } from "@/lib/utils";
import {
  getConfidenceLevel,
  getConfidenceColor,
  ASSESSMENT_TYPES,
  type AssessmentExtraction,
} from "@/types/extraction";
import type { Assessment } from "@/types/database";
import type { UpdateAssessmentInput } from "@/lib/api";

interface AssessmentTableProps {
  assessments: AssessmentExtraction[];
  dbAssessments: Assessment[];
  onUpdate: (index: number, updates: UpdateAssessmentInput) => void;
  onAcceptRow: (index: number) => void;
  hideConfidence?: boolean;
}

function parseLocalDate(dateStr: string): Date {
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(year, month - 1, day);
}

const ONGOING_PATTERNS = new Set([
  "ongoing", "throughout semester", "continuous", "weekly", "every class",
  "every week", "all semester", "throughout the semester",
]);

function isOngoing(db: Assessment): boolean {
  return (
    !db.due_date &&
    !db.is_date_ambiguous &&
    !!db.due_date_raw &&
    ONGOING_PATTERNS.has(db.due_date_raw.trim().toLowerCase())
  );
}

function getRowMinConfidence(a: AssessmentExtraction): number {
  return Math.min(
    a.title.confidence,
    a.type.confidence,
    a.weight_percent.confidence,
    a.due_date_resolved.confidence,
  );
}

type EditingCell = { row: number; col: string } | null;

export function AssessmentTable({
  assessments,
  dbAssessments,
  onUpdate,
  onAcceptRow,
  hideConfidence,
}: AssessmentTableProps) {
  const [editingCell, setEditingCell] = useState<EditingCell>(null);
  const [editValue, setEditValue] = useState("");
  const [editDialogIndex, setEditDialogIndex] = useState<number | null>(null);

  function startEdit(row: number, col: string, currentValue: string) {
    setEditingCell({ row, col });
    setEditValue(currentValue);
  }

  function commitTitleEdit(row: number) {
    setEditingCell(null);
    if (editValue !== dbAssessments[row]?.title) {
      onUpdate(row, { title: editValue });
    }
  }

  function commitWeightEdit(row: number) {
    setEditingCell(null);
    const num = parseFloat(editValue);
    onUpdate(row, { weight_percent: isNaN(num) ? null : num });
  }

  function handleTypeChange(row: number, value: string) {
    onUpdate(row, { type: value });
  }

  function handleDateSelect(row: number, date: Date | undefined) {
    if (!date) return;
    onUpdate(row, {
      due_date: format(date, "yyyy-MM-dd"),
      due_date_raw: null,
      is_date_ambiguous: false,
    });
  }

  function handleSetOngoing(row: number) {
    onUpdate(row, {
      due_date: null,
      due_date_raw: "Ongoing",
      is_date_ambiguous: false,
    });
  }

  function handleKeyDown(
    e: React.KeyboardEvent,
    row: number,
    commitFn: (row: number) => void,
  ) {
    if (e.key === "Enter") commitFn(row);
    if (e.key === "Escape") setEditingCell(null);
  }

  function handleDialogSave(updates: UpdateAssessmentInput) {
    if (editDialogIndex !== null) {
      onUpdate(editDialogIndex, updates);
      setEditDialogIndex(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Assessments</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Title</TableHead>
              <TableHead className="w-28">Type</TableHead>
              <TableHead className="w-36">Due Date</TableHead>
              <TableHead className="w-24">Weight</TableHead>
              {!hideConfidence && <TableHead className="w-28">Confidence</TableHead>}
              <TableHead className={hideConfidence ? "w-12" : "w-20"}>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {assessments.map((a, i) => {
              const db = dbAssessments[i];
              if (!db) return null;

              const minConf = getRowMinConfidence(a);
              const level = getConfidenceLevel(minConf);
              const rowColor = hideConfidence ? "" : getConfidenceColor(level);
              const isAmbiguous = db.is_date_ambiguous;
              const ongoing = isOngoing(db);

              return (
                <TableRow key={db.id} className={cn(!hideConfidence && "border-l-4", rowColor)}>
                  {/* Title */}
                  <TableCell>
                    {editingCell?.row === i && editingCell.col === "title" ? (
                      <Input
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onBlur={() => commitTitleEdit(i)}
                        onKeyDown={(e) =>
                          handleKeyDown(e, i, commitTitleEdit)
                        }
                        autoFocus
                        className="h-7 text-sm"
                      />
                    ) : (
                      <div className="flex items-center gap-1">
                        <span
                          className="cursor-pointer hover:underline"
                          onClick={() =>
                            startEdit(i, "title", db.title)
                          }
                        >
                          {db.title}
                        </span>
                        {!hideConfidence && a.title.source_text && (
                          <ConfidenceIndicator
                            confidence={a.title.confidence}
                            sourceText={a.title.source_text}
                            className="[&>span]:hidden"
                          />
                        )}
                      </div>
                    )}
                  </TableCell>

                  {/* Type */}
                  <TableCell>
                    <Select
                      value={db.type}
                      onValueChange={(v) => handleTypeChange(i, v)}
                    >
                      <SelectTrigger className="h-7 text-xs w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ASSESSMENT_TYPES.map((t) => (
                          <SelectItem key={t} value={t}>
                            {t.charAt(0).toUpperCase() + t.slice(1)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>

                  {/* Due Date */}
                  <TableCell>
                    <div className="flex flex-col gap-1">
                      {ongoing ? (
                        <Popover>
                          <PopoverTrigger asChild>
                            <Badge
                              variant="outline"
                              className="text-xs text-blue-700 border-blue-300 bg-blue-50 cursor-pointer hover:bg-blue-100 transition-colors"
                            >
                              Ongoing
                            </Badge>
                          </PopoverTrigger>
                          <PopoverContent
                            className="w-auto p-0"
                            align="start"
                          >
                            <Calendar
                              mode="single"
                              onSelect={(d) => handleDateSelect(i, d)}
                              initialFocus
                            />
                          </PopoverContent>
                        </Popover>
                      ) : (
                        <>
                          <Popover>
                            <PopoverTrigger asChild>
                              <Button
                                variant="outline"
                                size="sm"
                                className={cn(
                                  "h-7 text-xs justify-start font-normal",
                                  isAmbiguous &&
                                    "border-amber-400 text-amber-700",
                                  !db.due_date && "text-muted-foreground",
                                )}
                              >
                                {isAmbiguous && (
                                  <AlertTriangle className="mr-1 h-3 w-3 text-amber-500" />
                                )}
                                {db.due_date ? (
                                  <>
                                    <CalendarIcon className="mr-1 h-3 w-3" />
                                    {format(
                                      parseLocalDate(db.due_date),
                                      "MMM d, yyyy",
                                    )}
                                  </>
                                ) : (
                                  "Pick date"
                                )}
                              </Button>
                            </PopoverTrigger>
                            <PopoverContent
                              className="w-auto p-0"
                              align="start"
                            >
                              <Calendar
                                mode="single"
                                selected={
                                  db.due_date
                                    ? parseLocalDate(db.due_date)
                                    : undefined
                                }
                                onSelect={(d) => handleDateSelect(i, d)}
                                initialFocus
                              />
                              <div className="border-t px-3 py-2">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="w-full text-xs text-blue-700 hover:text-blue-800 hover:bg-blue-50"
                                  onClick={() => handleSetOngoing(i)}
                                >
                                  Mark as Ongoing
                                </Button>
                              </div>
                            </PopoverContent>
                          </Popover>
                          {isAmbiguous && db.due_date_raw && (
                            <span className="text-[10px] text-amber-600 leading-tight">
                              Original: &ldquo;{db.due_date_raw}&rdquo;
                            </span>
                          )}
                        </>
                      )}
                    </div>
                  </TableCell>

                  {/* Weight */}
                  <TableCell>
                    {editingCell?.row === i &&
                    editingCell.col === "weight" ? (
                      <Input
                        type="number"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onBlur={() => commitWeightEdit(i)}
                        onKeyDown={(e) =>
                          handleKeyDown(e, i, commitWeightEdit)
                        }
                        autoFocus
                        className="h-7 text-sm w-20"
                      />
                    ) : (
                      <span
                        className="cursor-pointer hover:underline"
                        onClick={() =>
                          startEdit(
                            i,
                            "weight",
                            String(db.weight_percent ?? ""),
                          )
                        }
                      >
                        {db.weight_percent != null
                          ? `${db.weight_percent}%`
                          : "—"}
                      </span>
                    )}
                  </TableCell>

                  {/* Confidence */}
                  {!hideConfidence && (
                    <TableCell>
                      <ConfidenceIndicator
                        confidence={minConf}
                        sourceText={a.title.source_text}
                      />
                    </TableCell>
                  )}

                  {/* Actions */}
                  <TableCell>
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => setEditDialogIndex(i)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      {!hideConfidence && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-green-600 hover:text-green-700"
                          onClick={() => onAcceptRow(i)}
                        >
                          <Check className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>

        {/* Edit dialog */}
        {editDialogIndex !== null && dbAssessments[editDialogIndex] && (
          <AssessmentEditDialog
            open={editDialogIndex !== null}
            onOpenChange={(open) => {
              if (!open) setEditDialogIndex(null);
            }}
            assessment={dbAssessments[editDialogIndex]}
            onSave={handleDialogSave}
          />
        )}
      </CardContent>
    </Card>
  );
}
