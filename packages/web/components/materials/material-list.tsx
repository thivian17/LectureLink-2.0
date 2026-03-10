"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Plus, FileText } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MaterialTypeBadge } from "@/components/materials/material-type-badge";
import { ErrorState } from "@/components/error-state";
import { listMaterials, AuthError, RateLimitError } from "@/lib/api";
import {
  MATERIAL_TYPE_LABELS,
  type CourseMaterial,
  type MaterialType,
} from "@/types/database";

interface MaterialListProps {
  courseId: string;
  courseName: string;
}

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  completed: "default",
  processing: "secondary",
  pending: "outline",
  failed: "destructive",
};

export function MaterialList({ courseId, courseName }: MaterialListProps) {
  const router = useRouter();
  const [materials, setMaterials] = useState<CourseMaterial[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [filterType, setFilterType] = useState<string>("all");

  const loadMaterials = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const typeFilter =
        filterType !== "all" ? (filterType as MaterialType) : undefined;
      const data = await listMaterials(courseId, typeFilter);
      setMaterials(data.materials);
    } catch (err) {
      const e =
        err instanceof Error ? err : new Error("Failed to load materials");
      setError(e);
      if (err instanceof AuthError) {
        toast.error("Session expired. Please log in again.");
        router.push("/login");
        return;
      }
      if (err instanceof RateLimitError) {
        toast.error(
          `Rate limit reached. Try again in ${Math.ceil(err.retryAfterSeconds / 60)} min.`,
        );
        return;
      }
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }, [courseId, filterType, router]);

  useEffect(() => {
    let cancelled = false;
    loadMaterials().then(() => {
      if (cancelled) return;
    });
    return () => {
      cancelled = true;
    };
  }, [loadMaterials]);

  if (loading) {
    return (
      <div className="space-y-6">
        <MaterialListHeader
          courseName={courseName}
          courseId={courseId}
          filterType={filterType}
          onFilterChange={setFilterType}
        />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="h-full">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-5 w-3/4" />
                    <Skeleton className="h-4 w-1/3" />
                  </div>
                  <Skeleton className="h-5 w-16 rounded-full" />
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <MaterialListHeader
          courseName={courseName}
          courseId={courseId}
          filterType={filterType}
          onFilterChange={setFilterType}
        />
        <ErrorState error={error} onRetry={loadMaterials} />
      </div>
    );
  }

  if (materials.length === 0) {
    return (
      <div className="space-y-6">
        <MaterialListHeader
          courseName={courseName}
          courseId={courseId}
          filterType={filterType}
          onFilterChange={setFilterType}
        />
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-16 text-center">
          <FileText className="h-12 w-12 text-muted-foreground/50" />
          <h3 className="mt-4 text-lg font-medium">No course materials yet</h3>
          <p className="mt-1 max-w-sm text-sm text-muted-foreground">
            No course materials uploaded yet. Upload readings, homework, and
            more to enhance your study experience.
          </p>
          <Button
            className="mt-6"
            onClick={() =>
              router.push(`/dashboard/courses/${courseId}/materials/new`)
            }
          >
            <Plus className="mr-2 h-4 w-4" />
            Upload Material
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <MaterialListHeader
        courseName={courseName}
        courseId={courseId}
        filterType={filterType}
        onFilterChange={setFilterType}
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {materials.map((material) => (
          <MaterialCard key={material.id} material={material} />
        ))}
      </div>
    </div>
  );
}

function MaterialCard({ material }: { material: CourseMaterial }) {
  const statusLabel =
    material.processing_status.charAt(0).toUpperCase() +
    material.processing_status.slice(1);

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <p className="font-medium truncate">{material.title}</p>
            {material.file_name && (
              <p className="text-xs text-muted-foreground truncate">
                {material.file_name}
              </p>
            )}
          </div>
          <MaterialTypeBadge type={material.material_type} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant={STATUS_VARIANT[material.processing_status] ?? "outline"}>
            {statusLabel}
          </Badge>
          {material.week_number && (
            <Badge variant="outline">Week {material.week_number}</Badge>
          )}
        </div>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          {material.concept_count > 0 && (
            <span>{material.concept_count} concepts</span>
          )}
          {material.chunk_count > 0 && (
            <span>{material.chunk_count} chunks</span>
          )}
          <span>
            {new Date(material.created_at).toLocaleDateString()}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

function MaterialListHeader({
  courseName,
  courseId,
  filterType,
  onFilterChange,
}: {
  courseName: string;
  courseId: string;
  filterType: string;
  onFilterChange: (value: string) => void;
}) {
  const router = useRouter();
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <h2 className="text-lg font-semibold">Materials</h2>
        <p className="text-sm text-muted-foreground">{courseName}</p>
      </div>
      <div className="flex items-center gap-2">
        <Select value={filterType} onValueChange={onFilterChange}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="All types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            {(
              Object.entries(MATERIAL_TYPE_LABELS) as [MaterialType, string][]
            ).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          onClick={() =>
            router.push(`/dashboard/courses/${courseId}/materials/new`)
          }
        >
          <Plus className="mr-2 h-4 w-4" />
          Upload Material
        </Button>
      </div>
    </div>
  );
}
