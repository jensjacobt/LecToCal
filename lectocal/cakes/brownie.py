from .cake import Cake

class Brownie(Cake):
    @staticmethod
    def get_name():
        return "Brownie"

    @staticmethod
    def get_taste():
        return "Great!"
