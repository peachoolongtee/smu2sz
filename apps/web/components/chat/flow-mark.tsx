import { FlowLogo } from "@/components/flow-logo";

/** FLOW's small mark beside its turns and in Ask FLOW's header: the logo on the lavender of the owner's palette. Decorative: the name is said in words beside it. */
export function FlowMark({ size = "sm" }: { size?: "sm" | "md" }) {
  return (
    <span aria-hidden className={`grid shrink-0 place-items-center rounded-pill bg-f-purple-soft ${size === "md" ? "size-9" : "size-7"}`} data-testid="flow-mark">
      <FlowLogo className={size === "md" ? "w-5" : "w-4"} />
    </span>
  );
}
