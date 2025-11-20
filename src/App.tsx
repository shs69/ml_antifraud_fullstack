import "./App.scss";
import { useAppDispatch, useAppSelector, useCheckAuth } from "./app/hooks";
import { Login } from "./features/Login/Login";
import { Home } from "./features/Home/Home";
import { selectToken, selectUser } from "./features/Login/LoginSlice";
import { CSSTransition } from "react-transition-group";
import { useEffect, useRef } from "react";
import { transactionsApi } from "./features/Transaction/TransactionApi";

export const App = () => {
  const appRef = useRef(null);
  const dispatch = useAppDispatch();
  useCheckAuth();

  const isLogged = useAppSelector(selectToken);
  const user = useAppSelector(selectUser);

  useEffect(() => {
    if (!!isLogged && !!user) {
      const sse = new EventSource("http://localhost:8000/transactions/sse");

      sse.onmessage = () => {
        dispatch(transactionsApi.util.invalidateTags(["Transaction"]));
      };

      return () => {
        sse.close();
      };
    }
  });

  return (
    <div className="App">
      {!isLogged && !user && <Login />}
      <CSSTransition
        in={Boolean(isLogged && user)}
        timeout={300}
        classNames="fade"
        unmountOnExit
        nodeRef={appRef}
      >
        <Home user={user} ref={appRef} />
      </CSSTransition>
    </div>
  );
};
