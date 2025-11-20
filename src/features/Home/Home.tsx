import { TransactionList } from "../ui/TransactionsList/TransactionList";
import { Row } from "../ui/HomeRow/Row";
import { RowElem } from "../ui/RowElement/RowElem";
import {
  transactionsApi,
  useGetTransactionsQuery,
} from "../Transaction/TransactionApi";
import { RowBtn } from "../ui/RowElementLogout/RowBtn";
import { useAppDispatch, useAppSelector } from "../../app/hooks";
import { logout } from "../Login/LoginSlice";
import {
  openWindow,
  selectCreateWindowOpen,
} from "../Transaction/TransactionSlice";
import { forwardRef, useRef, type JSX } from "react";
import type { LoginType } from "../../interfaces";
import "./Home.scss";
import { CreateTransaction } from "../Transaction/CreateTransaction/CreateTransaction";
import { CSSTransition } from "react-transition-group";
import { authApi } from "../Login/LoginApi";

export const Home = forwardRef<HTMLDivElement, { user: LoginType["user"] }>(
  ({ user }, ref): JSX.Element => {
    const nodeRef = useRef(null);
    const dispatch = useAppDispatch();
    const isOpenWindow = useAppSelector(selectCreateWindowOpen);

    const openWindowFn = () => {
      dispatch(openWindow());
    };

    const logoutFn = () => {
      dispatch(logout());
      dispatch(transactionsApi.util.resetApiState());
      dispatch(authApi.util.resetApiState());
    };

    let { data } = useGetTransactionsQuery({
      offset: 0,
      limit: 1,
    });

    data ??= { count: NaN, data: [] };

    return (
      <div className="home" ref={ref}>
        <div className="home__cont">
          <Row>
            <RowElem
              name="Привествуем,"
              value={user ? user.full_name : "null"}
            ></RowElem>
            <RowElem
              name="Количество операций"
              value={data.count.toString()}
            ></RowElem>
            <RowElem name="Мошеннических операций:" value="1"></RowElem>
            <RowBtn value="Добавить транзакцию" onClick={openWindowFn}></RowBtn>
            <RowBtn onClick={logoutFn} value="Выйти нахуй" />
          </Row>
          <TransactionList userTransactionsCount={data.count} />
          <CSSTransition
            in={isOpenWindow}
            timeout={200}
            classNames="fade"
            unmountOnExit
            nodeRef={nodeRef}
          >
            <CreateTransaction ref={nodeRef} />
          </CSSTransition>
        </div>
      </div>
    );
  },
);
