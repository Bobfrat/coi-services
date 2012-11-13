from pyon.public import Container, ImmediateProcess
from interface.services.examples.bank.ibank_service import BankServiceProcessClient
from pyon.util.context import LocalContextMixin
from interface.services.icontainer_agent import ContainerAgentProcessClient

class FakeProcess(LocalContextMixin):
    name = 'bank_client'
    id = 'bank_client'


class BankClientProcess(ImmediateProcess):
    """

    """
    def on_init(self):
        pass

    def on_start(self):

        container_name = self.CFG.get("kill_container", None)

        run_client(self.container, )

        if container_name:
            cc_client = ContainerAgentProcessClient(node=self.container.node, process=self, name=container_name)
            cc_client.stop()


    def on_quit(self):
        pass

def run_client(container, process=FakeProcess()):
    """
    This method will establish a Process RPC client endpoint to the Bank service and send a series of requests.
    """
    #client = ProcessRPCClient(node=container.node, name="bank", iface=IBankService, process=FakeProcess())
    client = BankServiceProcessClient(node=container.node, process=process)
    print 'Process RPC endpoint created'

    print 'Creating savings account'
    savingsAcctNum = client.new_account('kurt', 'Savings')
    print "New savings account number: " + str(savingsAcctNum)
    print "Starting savings balance %s" % str(client.get_balances(savingsAcctNum))
    client.deposit(savingsAcctNum, 99999999)
    print "Savings balance after deposit %s" % str(client.get_balances(savingsAcctNum))
    client.withdraw(savingsAcctNum, 1000)
    print "Savings balance after withdrawal %s" % str(client.get_balances(savingsAcctNum))

    print "Buying 1000 savings bonds"
    client.buy_bonds(savingsAcctNum, 1000)
    print "Savings balance after bond purchase %s" % str(client.get_balances(savingsAcctNum))

    checkingAcctNum = client.new_account('kurt', 'Checking')
    print "New checking account number: " + str(checkingAcctNum)
    print "Starting checking balance %s" % str(client.get_balances(checkingAcctNum))
    client.deposit(checkingAcctNum, 99999999)
    print "Confirming checking balance after deposit %s" % str(client.get_balances(checkingAcctNum))
    client.withdraw(checkingAcctNum, 1000)
    print "Confirming checking balance after withdrawal %s" % str(client.get_balances(checkingAcctNum))

    acctList = client.list_accounts('kurt')
    for acct_obj in acctList:
        print "Account: " + str(acct_obj)




if __name__ == '__main__':

    container = Container()
    container.start() # :(
    run_client(container)
    container.stop()
