import type { JSX } from "react";
import "./RowElem.scss";
import type { RowElemProps } from "../../../interfaces";

export const RowElem = ({
  name,
  value,
  fontSize,
}: RowElemProps): JSX.Element => {
  return (
    <div className="row_element">
      <div className="row_element__name">{name}</div>
      <div className="row_element__value" style={{ fontSize: fontSize }}>
        {value}
      </div>
    </div>
  );
};
