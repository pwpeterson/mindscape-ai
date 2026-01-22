import type { ConportProgressEntry } from "../api/conport";

export type ProgressTreeNode = {
    entry: ConportProgressEntry;
    children: ProgressTreeNode[];
};

/**
 * WBS metadata structure (stored in custom_data category='wbs_meta', key='progress:<ID>')
 * Based on product_context.wbs_schema v1.0
 */
export type WbsMeta = {
    entity_type: "project" | "phase" | "task";
    title: string;
    priority?: "P0" | "P1" | "P2" | "P3";
    tags?: string[];
    owner?: string;
    estimate_points?: number;
    due_date?: string;
    order?: number;
    external_refs?: Record<string, string>;
};

/**
 * Enhanced progress entry with WBS metadata
 */
export type ProgressEntryWithWbs = ConportProgressEntry & {
    wbs_meta?: WbsMeta;
};

/**
 * Tree node with WBS metadata
 */
export type ProgressTreeNodeWithWbs = {
    entry: ProgressEntryWithWbs;
    children: ProgressTreeNodeWithWbs[];
};
