import type { JSX } from "react";
import "./RowBtn.scss";

export const RowBtn = (props: {
  onClick: () => void;
  value: string;
  style?: {
    alignItems?: string;
    backgroundColor?: string;
    color?: string;
    outline?: string;
    outlineOffset?: string;
  };
}): JSX.Element => {
  return (
    <div className="row_btn" onClick={props.onClick} style={props.style}>
      <div className="row_btn__name">{props.value}</div>
    </div>
  );
};
