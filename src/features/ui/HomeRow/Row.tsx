import type { JSX } from "react"
import "./Row.scss"
import type { RowProps } from "../../../interfaces"

export const Row = ({ children }: RowProps): JSX.Element => {
  return <div className="row">{children}</div>
}
