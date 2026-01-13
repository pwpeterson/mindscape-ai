import type { ConportProgressEntry } from "../api/conport";

export type ProgressTreeNode = {
    entry: ConportProgressEntry;
    children: ProgressTreeNode[];
};