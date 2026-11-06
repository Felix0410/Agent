/** 只读目录不包含服务端地址、凭据、路径或执行入口。 */
import { request } from "../api";
export type ToolCapability = {
  name: string;
  source: "builtin" | "mcp" | "skill";
  permission: string;
  origin: string;
  availability: string;
};
export type SkillCapability = {
  name: string;
  description: string;
  required_tools: string[];
  availability: string;
};
export const getTools = (): Promise<ToolCapability[]> => request("/api/tools");
export const getSkills = (): Promise<SkillCapability[]> =>
  request("/api/skills");
