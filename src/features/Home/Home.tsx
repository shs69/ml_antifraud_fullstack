import { forwardRef, useRef, type JSX } from "react";
import { useNavigate } from "react-router-dom";
import { useAppDispatch, useAppSelector } from "../../app/hooks";
import { TransactionList } from "../ui/TransactionsList/TransactionList";
import { Row } from "../ui/HomeRow/Row";
import { RowElem } from "../ui/RowElement/RowElem";
import {
  transactionsApi,
  useGetTransactionsQuery,
} from "../Transaction/TransactionApi";
import { RowBtn } from "../ui/RowElementBtn/RowBtn";
import { NotificationElem } from "../ui/Notification/Notification";
import { logout, selectUser } from "../Login/LoginSlice";
import {
  openWindow,
  selectCreateWindowOpen,
  selectDetailsWindowOpen,
} from "../Transaction/TransactionSlice";
import { resetNotification } from "../ui/Notification/NotificationSlice";
import { authApi } from "../Login/LoginApi";
import { CreateTransaction } from "../Transaction/CreateTransaction/CreateTransaction";
import { CSSTransition } from "react-transition-group";
import "./Home.scss";
import { TransactionWindow } from "../Transaction/DetailsTransaction/TransactionWindow.tsx";

export const Home = forwardRef<HTMLDivElement>((_, ref): JSX.Element => {
  const nodeRef = useRef(null);
  const nodeRef2 = useRef(null);
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const isOpenWindow = useAppSelector(selectCreateWindowOpen);
  const isDetailsOpen = useAppSelector(selectDetailsWindowOpen);
  const user = useAppSelector(selectUser);
  const skipQuery = !user;

  const openWindowFn = () => {
    dispatch(openWindow());
  };

  const logoutFn = () => {
    dispatch(logout());
    dispatch(resetNotification());
    dispatch(transactionsApi.util.resetApiState());
    dispatch(authApi.util.resetApiState());
    void navigate("/login");
  };

  let { data } = useGetTransactionsQuery(
    {
      offset: 0,
      limit: 1,
    },
    { skip: skipQuery },
  );

  data ??= { count: NaN, fraud_count: NaN, data: [] };

  return (
    <div className="home" ref={ref}>
      <div className="home__cont">
        <NotificationElem />
        <Row>
          <RowElem
            name="Привествуем,"
            value={user ? user.full_name : "null"}
          ></RowElem>
          <RowElem
            name="Количество операций"
            value={data.count.toString()}
          ></RowElem>
          <RowElem
            name="Мошеннических операций:"
            value={data.fraud_count.toString()}
          ></RowElem>
          <RowBtn value="Добавить транзакцию" onClick={openWindowFn}></RowBtn>
          <RowBtn onClick={logoutFn} value="Выйти" />
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
        <CSSTransition
          in={isDetailsOpen}
          timeout={200}
          classNames="fade"
          unmountOnExit
          nodeRef={nodeRef2}
        >
          <TransactionWindow ref={nodeRef2} />
        </CSSTransition>
      </div>
    </div>
  );
});
